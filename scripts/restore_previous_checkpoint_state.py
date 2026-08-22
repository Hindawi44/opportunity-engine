#!/usr/bin/env python3
"""Restore durable checkpoint state before discovery.

This phase restores prior SQLite/learning continuity and exposes only explicitly
promoted query terms to the current discovery run. New learning is intentionally
deferred until the post-bulletin capture stage so a missed opportunity found
today can enter the learning cycle today rather than waiting for tomorrow.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from opportunity_engine.discovery import checkpoint_state_restore
from opportunity_engine.learned_query_overlay import (
    build_learned_query_overlay,
    load_learned_query_overlay,
    merge_learned_query_overlays,
    save_learned_query_overlay,
)
from opportunity_engine.learning_promotion_gate import (
    load_query_promotion_decisions,
    select_promoted_query_overlay,
)


ITALY_MEMORY_RELATIVE_PATH = "it-market/opportunity_engine.db"
NETHERLANDS_MEMORY_RELATIVE_PATH = "nl-market/opportunity_engine.db"
FRANCE_MEMORY_RELATIVE_PATH = "fr-market/opportunity_engine.db"
SHADOW_KEYWORD_OVERLAY_FILENAME = "shadow-keyword-overlay.json"
DEFAULT_PROMOTION_CONFIG_PATH = Path("config/learning/query_promotions.json")
DEFAULT_SHADOW_BOOTSTRAP_PATH = Path(
    "config/learning/promoted_query_shadow_bootstrap.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    parser.add_argument(
        "--current-run-id",
        type=int,
        default=int(os.environ.get("GITHUB_RUN_ID", "0") or 0),
    )
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--status-path", required=True)
    parser.add_argument(
        "--workflow-file",
        default="multi-market-daily-operator-checkpoint.yaml",
    )
    parser.add_argument("--branch", default="main")
    return parser.parse_args()


def _write_status(path: Path, status: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_optional_overlay(path: Path) -> dict:
    if not path.exists():
        return build_learned_query_overlay([])
    return load_learned_query_overlay(path)


def _prepare_previous_runtime_overlay(
    input_root: Path,
    runtime_overlay: Path,
    *,
    promotion_config_path: str | Path = DEFAULT_PROMOTION_CONFIG_PATH,
    bootstrap_shadow_path: str | Path = DEFAULT_SHADOW_BOOTSTRAP_PATH,
) -> None:
    """Rebuild current Production overlay from durable proof + current decisions.

    Restored Shadow evidence is authoritative learning memory. The prior active
    overlay may contribute compatible proof metadata, but can never activate a
    term by itself. A small repository bootstrap preserves the already-audited
    V15C repeated-transfer proof across the migration into the scheduled runtime.
    The bootstrap is Shadow evidence only: the explicit promotion gate still
    decides whether any term becomes active.
    """
    learning_dir = input_root / "learning"
    shadow_path = learning_dir / SHADOW_KEYWORD_OVERLAY_FILENAME
    previous_active_path = learning_dir / "active-keyword-overlay.json"
    bootstrap_path = Path(bootstrap_shadow_path)

    restored_shadow = _load_optional_overlay(shadow_path)
    previous_active = _load_optional_overlay(previous_active_path)
    bootstrap_shadow = _load_optional_overlay(bootstrap_path)

    evidence = merge_learned_query_overlays(
        merge_learned_query_overlays(restored_shadow, previous_active),
        bootstrap_shadow,
    )

    # Persist the merged Shadow proof into this run's durable input state so the
    # normal post-capture learner and the next checkpoint inherit the same proof.
    save_learned_query_overlay(shadow_path, evidence)

    decisions = load_query_promotion_decisions(promotion_config_path)
    active = select_promoted_query_overlay(evidence, decisions)

    # select_promoted_query_overlay is fail-closed and can never invent a term:
    # every active row must already be PROVEN evidence and explicitly PROMOTED.
    save_learned_query_overlay(runtime_overlay, active)


def main() -> int:
    args = parse_args()
    extra_paths = (
        ITALY_MEMORY_RELATIVE_PATH,
        NETHERLANDS_MEMORY_RELATIVE_PATH,
        FRANCE_MEMORY_RELATIVE_PATH,
    )
    for relative_path in extra_paths:
        if relative_path not in checkpoint_state_restore.DATABASE_RELATIVE_PATHS:
            checkpoint_state_restore.DATABASE_RELATIVE_PATHS = (
                *checkpoint_state_restore.DATABASE_RELATIVE_PATHS,
                relative_path,
            )
    if SHADOW_KEYWORD_OVERLAY_FILENAME not in checkpoint_state_restore.LEARNING_STATE_FILENAMES:
        checkpoint_state_restore.LEARNING_STATE_FILENAMES = (
            *checkpoint_state_restore.LEARNING_STATE_FILENAMES,
            SHADOW_KEYWORD_OVERLAY_FILENAME,
        )

    status = checkpoint_state_restore.restore_previous_checkpoint_databases(
        repository=args.repository,
        token=args.token,
        current_run_id=args.current_run_id,
        input_root=args.input_root,
        status_path=args.status_path,
        workflow_file=args.workflow_file,
        branch=args.branch,
    )

    input_root = Path(args.input_root)
    runtime_overlay = Path("learning") / "active-keyword-overlay.json"
    learning_report_path = Path(args.status_path).parent / "daily-learning-cycle.json"

    try:
        _prepare_previous_runtime_overlay(input_root, runtime_overlay)
    except Exception as exc:
        if runtime_overlay.exists():
            runtime_overlay.unlink()
        status["previous_learning_overlay_prepare_error"] = {
            "error_type": type(exc).__name__,
            "error": str(exc)[:500],
        }

    status["daily_learning_cycle"] = {
        "status": "DEFERRED_UNTIL_POST_CAPTURE",
        "reason": (
            "learning runs after source verification and automatic miss capture "
            "so today's verified miss can be consumed in the same daily run"
        ),
        "consumer": "daily_auto_miss_learning_cli_hook",
        "learning_search_requests": 0,
        "report_path": learning_report_path.as_posix(),
        "runtime_overlay_path": runtime_overlay.as_posix(),
        "automatic_query_activation": False,
        "promotion_gate_enforced": True,
    }

    _write_status(Path(args.status_path), status)
    print(json.dumps(status, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
