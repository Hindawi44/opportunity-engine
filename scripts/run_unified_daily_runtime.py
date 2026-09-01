#!/usr/bin/env python3
"""Build the visible six-market runtime after the daily bulletin is complete."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from opportunity_engine.discovery.unified_daily_runtime import (
    build_unified_daily_runtime,
)


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
    paths = build_unified_daily_runtime(Path(args.output_dir))
    print(f"unified_daily_pipeline: {paths['pipeline']}")
    print(f"unified_daily_runtime: {paths['runtime']}")
    print(f"unified_daily_summary: {paths['summary']}")
    print(f"unified_daily_reconciliation: {paths['reconciliation']}")
    print(f"unified_operator_report_json: {paths['operator_report_json']}")
    print(f"unified_operator_report_text: {paths['operator_report_text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
