#!/usr/bin/env python3
"""Restore durable checkpoint state and prepare bounded learning for this run."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from opportunity_engine.daily_learning_operator import DailyLearningPolicy
from opportunity_engine.daily_learning_runtime import run_daily_learning_runtime
from opportunity_engine.discovery import checkpoint_state_restore
from opportunity_engine.learned_query_overlay import (
    load_learned_query_overlay,
    save_learned_query_overlay,
)


ITALY_MEMORY_RELATIVE_PATH = "it-market/opportunity_engine.db"
NETHERLANDS_MEMORY_RELATIVE_PATH = "nl-market/opportunity_engine.db"
FRANCE_MEMORY_RELATIVE_PATH = "fr-market/opportunity_engine.db"


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


def _prepare_previous_runtime_overlay(input_root: Path, runtime_overlay: Path) -> None:
    """Expose yesterday's proven overlay even if today's learning step fails."""
    durable_overlay = input_root / "learning" / "active-keyword-overlay.json"
    if not durable_overlay.exists():
        if runtime_overlay.exists():
            runtime_overlay.unlink()
        return
    overlay = load_learned_query_overlay(durable_overlay)
    save_learned_query_overlay(runtime_overlay, overlay)


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
    learning_dir = Path(args.input_root) / "learning"
    runtime_overlay = Path("learning") / "active-keyword-overlay.json"
    learning_report_path = Path(args.status_path).parent / "daily-learning-cycle.json"

    try:
        _prepare_previous_runtime_overlay(input_root, runtime_overlay)
    except Exception as exc:
        status["previous_learning_overlay_prepare_error"] = {
            "error_type": type(exc).__name__,
            "error": str(exc)[:500],
        }

    try:
        learning_report = run_daily_learning_runtime(
            learning_dir=learning_dir,
            inbox_path="config/learning/missed_opportunity_inbox.json",
            active_query_config="config/brave_search_queries.json",
            report_path=learning_report_path,
            runtime_overlay_path=runtime_overlay,
            environment=os.environ,
            policy=DailyLearningPolicy(
                max_candidates_per_run=2,
                min_recovered_cases=1,
                min_precision=0.20,
                max_terms_per_market=5,
            ),
            results_per_candidate=5,
        )
        status["daily_learning_cycle"] = {
            "status": learning_report.get("search_status"),
            "known_missed_opportunity_count": learning_report.get(
                "known_missed_opportunity_count", 0
            ),
            "candidate_count": learning_report.get("candidate_count", 0),
            "learning_search_requests": learning_report.get(
                "learning_search_requests", 0
            ),
            "proven_term_count_this_run": learning_report.get(
                "proven_term_count_this_run", 0
            ),
            "active_learned_term_count": learning_report.get(
                "active_learned_term_count", 0
            ),
            "report_path": learning_report_path.as_posix(),
            "runtime_overlay_path": runtime_overlay.as_posix(),
        }
    except Exception as exc:
        # The project must keep yesterday's proven skills and core discovery even
        # if today's learning iteration cannot run. Learning failure is visible,
        # never silently converted to an empty success.
        status["daily_learning_cycle"] = {
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc)[:500],
            "learning_search_requests": 0,
            "report_path": learning_report_path.as_posix(),
            "runtime_overlay_path": runtime_overlay.as_posix(),
        }

    _write_status(Path(args.status_path), status)
    print(json.dumps(status, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
