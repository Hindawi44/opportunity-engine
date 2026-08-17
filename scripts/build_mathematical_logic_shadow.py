#!/usr/bin/env python3
"""Build the read-only Mathematical Logic V1 shadow artifact."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for candidate in (ROOT, SRC):
    text = str(candidate)
    if text not in sys.path:
        sys.path.insert(0, text)

from opportunity_engine.discovery.mathematical_logic_shadow import (
    OUTPUT_FILENAME,
    write_mathematical_logic_shadow,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="artifacts/multi-market-daily-operator-checkpoint",
    )
    parser.add_argument(
        "--baseline-commit",
        default=os.environ.get("GITHUB_SHA") or None,
        help="Exact commit whose current project output is being represented.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    report = write_mathematical_logic_shadow(
        output_dir,
        baseline_commit=args.baseline_commit,
    )
    print(
        json.dumps(
            {
                "status": "SUCCESS",
                "engine_version": report.get("engine_version"),
                "case_count": (report.get("baseline") or {}).get("observed_case_count"),
                "coverage_matches": (report.get("baseline") or {}).get(
                    "coverage_matches_declared_count"
                ),
                "mean_completeness": ((report.get("aggregate") or {}).get("all_cases") or {}).get(
                    "mean_completeness"
                ),
                "decision_influence": (report.get("methodology") or {}).get("decision_influence"),
                "output": (output_dir / OUTPUT_FILENAME).as_posix(),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
