#!/usr/bin/env python3
"""Run P1 end-to-end stages with the unified P2 scoring and alert stages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_end_to_end_pipeline import STAGES, load_json, run_pipeline, write_json_atomic


SCORING_STAGE = (
    "unified_scoring",
    (
        "scripts/build_scored_opportunities.py",
        "--queue",
        "data/opportunity_review_queue.json",
        "--evaluations",
        "data/economic_evaluation_queue.json",
        "--output",
        "data/scored_opportunities.json",
        "--history",
        "data/scoring_history.json",
    ),
)

TOP5_STAGE = (
    "top5_report",
    (
        "scripts/build_top5_opportunity_report.py",
        "--scored",
        "data/scored_opportunities.json",
        "--output",
        "data/top5_opportunities.json",
        "--limit",
        "5",
    ),
)

SCORING_ALERT_STAGE = (
    "scoring_alerts",
    (
        "scripts/build_scoring_alerts.py",
        "--scored",
        "data/scored_opportunities.json",
        "--alerts",
        "data/smart_alerts.json",
        "--limit",
        "5",
    ),
)


def build_p2_stages():
    stages = []
    for stage in STAGES:
        name = stage[0]
        if name == "top5_report":
            stages.extend((SCORING_STAGE, TOP5_STAGE, SCORING_ALERT_STAGE))
        else:
            stages.append(stage)
    return tuple(stages)


def enrich_daily_report(root: Path) -> None:
    report_path = root / "data/daily_report.json"
    if not report_path.exists():
        return
    report = load_json(report_path)
    if not isinstance(report, dict):
        raise ValueError("daily report must be an object")
    report["schema_version"] = 2
    report["scoring"] = load_json(root / "data/scored_opportunities.json")
    report["scoring_history_path"] = "data/scoring_history.json"
    write_json_atomic(report_path, report)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run P2 unified scoring pipeline")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    result = run_pipeline(root, stages=build_p2_stages(), dry_run=args.dry_run)
    if result == 0 and not args.dry_run:
        enrich_daily_report(root)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
