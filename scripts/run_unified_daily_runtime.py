#!/usr/bin/env python3
"""Build the visible six-market runtime after the daily bulletin is complete."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from opportunity_engine.discovery.unified_daily_runtime import (
    build_unified_daily_runtime,
)
from opportunity_engine.human_listing_review_queue import build_queue, readable_text
from opportunity_engine.operator_study_memory import export_memory


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default="artifacts/multi-market-daily-operator-checkpoint",
    )
    parser.add_argument("--input-root", default="artifacts/multi-market-inputs")
    args = parser.parse_args()

    os.environ["OUTPUT_DIR"] = args.output_dir
    os.environ["INPUT_ROOT"] = args.input_root
    output_dir = Path(args.output_dir)
    paths = build_unified_daily_runtime(output_dir)
    report_path = output_dir / "multi-market-daily-checkpoint.json"
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        memory = export_memory(Path(args.input_root))
        queue = build_queue(report, memory)
        (output_dir / "human-listing-review-queue-v1.json").write_text(
            json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        text = readable_text(queue)
        (output_dir / "human-listing-review-queue-v1.txt").write_text(text, encoding="utf-8")
        phone_summary = output_dir / "multi-market-phone-summary.txt"
        if phone_summary.is_file():
            with phone_summary.open("a", encoding="utf-8") as handle:
                handle.write("\n" + text)
        print("human_listing_review_queue:", queue["counts"])
    elif os.environ.get("GITHUB_ACTIONS") == "true":
        raise FileNotFoundError(f"Daily review source checkpoint is missing: {report_path}")
    print(f"unified_daily_pipeline: {paths['pipeline']}")
    print(f"unified_daily_runtime: {paths['runtime']}")
    print(f"unified_daily_summary: {paths['summary']}")
    print(f"unified_daily_reconciliation: {paths['reconciliation']}")
    print(f"unified_operator_report_json: {paths['operator_report_json']}")
    print(f"unified_operator_report_text: {paths['operator_report_text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())