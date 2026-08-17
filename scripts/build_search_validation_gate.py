#!/usr/bin/env python3
"""Build SEARCH_VALIDATION_GATE_V1 from saved JSON artifacts only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for candidate in (ROOT, SRC):
    text = str(candidate)
    if text not in sys.path:
        sys.path.insert(0, text)

from opportunity_engine.discovery.search_validation_gate import (
    CORE_MARKETS,
    SearchValidationPolicy,
    build_search_validation_report,
    load_observations,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir",
        action="append",
        required=True,
        help="Saved run artifact directory. Repeat for independent live runs.",
    )
    parser.add_argument(
        "--output",
        default="artifacts/search-validation/search-validation-gate-v1.json",
    )
    parser.add_argument(
        "--required-market",
        action="append",
        dest="required_markets",
        help="Core market required for overall proof. Defaults to NO, SE, DE.",
    )
    parser.add_argument("--min-live-runs", type=int, default=3)
    parser.add_argument("--min-retrieval-success-rate", type=float, default=0.80)
    parser.add_argument("--min-productive-run-rate", type=float, default=0.50)
    parser.add_argument("--min-verified-active-runs", type=int, default=2)
    args = parser.parse_args()

    policy = SearchValidationPolicy(
        min_live_runs=args.min_live_runs,
        min_retrieval_success_rate=args.min_retrieval_success_rate,
        min_productive_run_rate=args.min_productive_run_rate,
        min_verified_active_runs=args.min_verified_active_runs,
    )
    observations = load_observations(args.run_dir)
    report = build_search_validation_report(
        observations,
        policy=policy,
        required_markets=args.required_markets or CORE_MARKETS,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "SUCCESS",
                "overall_verdict": report["overall_verdict"],
                "progression_gate_open": report["progression_gate_open"],
                "observation_count": report["observation_count"],
                "external_api_calls": False,
                "brave_requests": 0,
                "output": output.as_posix(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
