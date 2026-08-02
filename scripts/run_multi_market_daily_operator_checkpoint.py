#!/usr/bin/env python3
"""Build one manual read-only operator checkpoint for NO, SE, and DE."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

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
    try:
        manifest = _load(Path(args.manifest))
        market_matrix = _load(Path(args.market_matrix))
        report = build_multi_market_checkpoint(
            manifest,
            market_matrix,
            root=Path(args.root),
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

    print(render_phone_summary(report), end="")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
