#!/usr/bin/env python3
"""Run one bounded durable missed-opportunity learning cycle."""
from __future__ import annotations

import argparse
import json

from opportunity_engine.daily_learning_operator import DailyLearningPolicy
from opportunity_engine.daily_learning_runtime import run_daily_learning_runtime


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--inbox",
        default="config/learning/missed_opportunity_inbox.json",
    )
    parser.add_argument("--learning-dir", required=True)
    parser.add_argument(
        "--active-query-config",
        default="config/brave_search_queries.json",
    )
    parser.add_argument(
        "--promotion-config",
        default="config/learning/query_promotions.json",
    )
    parser.add_argument("--report", required=True)
    parser.add_argument("--runtime-overlay")
    parser.add_argument("--max-candidates", type=int, default=2)
    parser.add_argument("--results-per-candidate", type=int, default=5)
    parser.add_argument("--min-precision", type=float, default=0.20)
    parser.add_argument("--max-active-terms-per-market", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_daily_learning_runtime(
        learning_dir=args.learning_dir,
        inbox_path=args.inbox,
        active_query_config=args.active_query_config,
        promotion_config_path=args.promotion_config,
        report_path=args.report,
        runtime_overlay_path=args.runtime_overlay,
        policy=DailyLearningPolicy(
            max_candidates_per_run=args.max_candidates,
            min_recovered_cases=1,
            min_precision=args.min_precision,
            max_terms_per_market=args.max_active_terms_per_market,
        ),
        results_per_candidate=args.results_per_candidate,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
