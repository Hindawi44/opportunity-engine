#!/usr/bin/env python3
"""Build one manual read-only operator checkpoint for NO, SE, and DE."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from opportunity_engine.discovery.italy_case_memory_adapter import (
    run_italy_case_memory_cycle,
)
from opportunity_engine.discovery.italy_exact_lot_verification import (
    ENGINE_VERSION as ITALY_EXACT_LOT_ENGINE_VERSION,
    run_italy_exact_lot_verification,
)
from opportunity_engine.discovery.italy_market_discovery import (
    collect_italy_market_signals,
)
from opportunity_engine.discovery.multi_market_operator_checkpoint import (
    CheckpointIntegrityError,
    build_multi_market_checkpoint,
    render_phone_summary,
    write_checkpoint_artifacts,
)


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CheckpointIntegrityError(f"Expected a JSON object: {path}")
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _checkpoint_input_root(manifest: dict[str, Any], root: Path) -> Path:
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise CheckpointIntegrityError("Manifest has no sources for input-root discovery")
    parents: set[Path] = set()
    for source in sources:
        if not isinstance(source, dict):
            continue
        artifact_dir = str(source.get("artifact_dir") or "").strip()
        if artifact_dir:
            parents.add((root / artifact_dir).parent)
    if len(parents) != 1:
        raise CheckpointIntegrityError("Manifest sources do not share one checkpoint input root")
    return parents.pop()


def _run_italy_memory_sidecar(
    *,
    manifest: dict[str, Any],
    root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Run Italy discovery + persistent follow-up outside canonical NO/SE/DE coverage."""
    input_root = _checkpoint_input_root(manifest, root)
    italy_input = input_root / "it-market"
    italy_input.mkdir(parents=True, exist_ok=True)

    if not str(os.environ.get("BRAVE_SEARCH_API_KEY") or "").strip():
        skipped = {
            "schema_version": "italy-memory-sidecar-1.0",
            "status": "SKIPPED_NO_API_KEY",
            "source_country": "IT",
            "canonical_market_coverage_unchanged": ["NO", "SE", "DE"],
            "promotion_to_opportunity_allowed": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_reservation": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }
        exact_skipped = {
            "schema_version": "italy-exact-lot-verification-1.0",
            "engine_version": ITALY_EXACT_LOT_ENGINE_VERSION,
            "status": "SKIPPED_NO_API_KEY",
            "source_country": "IT",
            "verified_active_exact_lot_lead_count": 0,
            "promotion_to_opportunity_allowed": False,
            "top5_eligible": False,
            "analysis_eligible": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_reservation": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }
        _write_json(output_dir / "italy-case-memory-v1.json", skipped)
        _write_json(output_dir / "italy-exact-lot-verification-v1.json", exact_skipped)
        skipped["exact_lot_verification"] = exact_skipped
        return skipped

    discovery = collect_italy_market_signals(environment=os.environ)
    _write_json(italy_input / "italy-market-discovery-v1.json", discovery)
    _write_json(output_dir / "italy-market-discovery-v1.json", discovery)

    current_signals = [
        item for item in discovery.get("signals") or [] if isinstance(item, dict)
    ]
    cycle = run_italy_case_memory_cycle(
        current_signals,
        input_root=input_root,
        environment=os.environ,
    )
    cycle["state_restore_owner"] = "MULTI_MARKET_DAILY_OPERATOR_CHECKPOINT"
    cycle["canonical_market_coverage_unchanged"] = ["NO", "SE", "DE"]
    cycle["discovery_status"] = discovery.get("status")
    cycle["discovery_accepted_signal_count"] = discovery.get("accepted_signal_count")

    exact_lot = run_italy_exact_lot_verification(
        dict(cycle.get("follow_up") or {}),
    )
    cycle["exact_lot_verification"] = {
        "engine_version": exact_lot.get("engine_version"),
        "status": exact_lot.get("status"),
        "candidate_lead_count": exact_lot.get("candidate_lead_count"),
        "source_page_verified_count": exact_lot.get("source_page_verified_count"),
        "verified_active_exact_lot_lead_count": exact_lot.get(
            "verified_active_exact_lot_lead_count"
        ),
        "output": "italy-exact-lot-verification-v1.json",
    }

    _write_json(output_dir / "italy-case-memory-v1.json", cycle)
    _write_json(
        output_dir / "italy-signal-follow-up-v1.json",
        dict(cycle.get("follow_up") or {}),
    )
    _write_json(
        output_dir / "italy-exact-lot-verification-v1.json",
        exact_lot,
    )
    return cycle


def _correct_review_reason(report: dict[str, Any]) -> None:
    """Keep the operator action reason aligned with the selected record state."""
    action = report.get("next_human_action")
    if not isinstance(action, dict):
        return
    if action.get("action") != "REVIEW_ONE_OPPORTUNITY":
        return

    identity = action.get("opportunity_identity")
    records = report.get("deduplicated_opportunities")
    if not isinstance(records, list):
        return

    target = next(
        (
            item
            for item in records
            if isinstance(item, dict)
            and item.get("opportunity_identity") == identity
        ),
        None,
    )
    if target is None:
        return

    if target.get("analysis_eligible") is True:
        action["reason"] = (
            "An active Top 5 opportunity is ready for human analysis review."
        )
    else:
        action["reason"] = (
            "An active Top 5 candidate requires human verification and evidence "
            "completion before analysis."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument(
        "--market-matrix",
        default="config/market_completion_matrix.json",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/multi-market-daily-operator-checkpoint",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Root used to resolve artifact_dir paths from the manifest",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    root = Path(args.root)
    try:
        manifest = _load(Path(args.manifest))
        market_matrix = _load(Path(args.market_matrix))
        report = build_multi_market_checkpoint(
            manifest,
            market_matrix,
            root=root,
        )
        _correct_review_reason(report)
        paths = write_checkpoint_artifacts(report, output_dir)
    except (OSError, json.JSONDecodeError, CheckpointIntegrityError) as exc:
        output_dir.mkdir(parents=True, exist_ok=True)
        error_path = output_dir / "multi-market-checkpoint-error.json"
        error_path.write_text(
            json.dumps(
                {
                    "status": "FAILED",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "automatic_contact": False,
                    "automatic_bid": False,
                    "automatic_purchase": False,
                    "automatic_payment": False,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"Checkpoint integrity failure: {exc}", file=sys.stderr)
        print(f"error_report: {error_path}", file=sys.stderr)
        return 2

    italy_sidecar = _run_italy_memory_sidecar(
        manifest=manifest,
        root=root,
        output_dir=output_dir,
    )

    print(render_phone_summary(report), end="")
    for name, path in paths.items():
        print(f"{name}: {path}")
    exact_summary = italy_sidecar.get("exact_lot_verification") or {}
    print(
        "italy_memory_sidecar: "
        + json.dumps(
            {
                "status": italy_sidecar.get("status") or "SUCCESS",
                "persistent_case_count": italy_sidecar.get("persistent_case_count", 0),
                "discovery_status": italy_sidecar.get("discovery_status"),
                "exact_lot_status": exact_summary.get("status"),
                "verified_active_exact_lot_lead_count": exact_summary.get(
                    "verified_active_exact_lot_lead_count", 0
                ),
                "automatic_purchase": italy_sidecar.get("automatic_purchase"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
