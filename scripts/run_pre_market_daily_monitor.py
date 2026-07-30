#!/usr/bin/env python3
"""Run one bounded daily pre-market clothing monitoring cycle."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from opportunity_engine.discovery.konkurs_app_clothing_adapter import (
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_PAGE_SIZE,
)
from opportunity_engine.discovery.pre_market_case_tracker import load_case_registry
from opportunity_engine.discovery.pre_market_daily_monitor import (
    SOURCE_TEMPORARILY_UNAVAILABLE,
    run_pre_market_daily_monitor,
    write_pre_market_daily_monitor_artifacts,
)
from opportunity_engine.discovery.pre_market_sale_channel_search import (
    DEFAULT_RESULTS_PER_QUERY,
    MAX_RESULTS_PER_QUERY,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--previous-registry",
        default="data/pre_market_cases.json",
        help="Durable registry from the previous run; a missing file starts cleanly",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/pre-market-daily-monitor"),
    )
    parser.add_argument("--case-limit", type=int, choices=range(1, 21), default=10)
    parser.add_argument(
        "--results-per-query",
        type=int,
        choices=range(1, MAX_RESULTS_PER_QUERY + 1),
        default=DEFAULT_RESULTS_PER_QUERY,
    )
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument(
        "--freshness",
        choices=("none", "pd", "pw", "pm", "py"),
        default="py",
    )
    parser.add_argument(
        "--fail-on-source-unavailable",
        action="store_true",
        help="Exit 2 after writing fail-closed artifacts when any source is incomplete",
    )
    args = parser.parse_args()

    api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("BRAVE_SEARCH_API_KEY is required")

    previous = load_case_registry(args.previous_registry)
    result = run_pre_market_daily_monitor(
        api_key=api_key,
        previous_cases=previous,
        case_limit=args.case_limit,
        results_per_query=args.results_per_query,
        lookback_days=args.lookback_days,
        page_size=args.page_size,
        freshness=None if args.freshness == "none" else args.freshness,
    )
    paths = write_pre_market_daily_monitor_artifacts(result, args.output_dir)

    print(f"Source status: {result.source_status}")
    print(f"Lead scan complete: {result.pilot.scan_complete}")
    print(f"Ranked leads: {len(result.pilot.leads)}")
    print(f"Selected cases: {len(result.pilot.review_top)}")
    print(f"Completed case scans: {len(result.completed_attempts)}")
    print(f"Temporarily unavailable case scans: {len(result.unavailable_attempts)}")
    print(f"Allocated query budget: {result.allocated_query_budget}")
    print(f"Requests made: {result.requests_made}")
    print(f"Cases retained: {len(result.tracker.cases)}")
    print(f"Material changes: {len(result.tracker.changes)}")
    print(f"Alerts: {len(result.tracker.alerts)}")
    print(f"Verified inventory sales: {len(result.tracker.verified_cases)}")
    print("Incomplete sources treated as no sale: false")
    print("Automatic page open/contact/bid/purchase/payment: false")
    for label, path in paths.items():
        print(f"{label}: {path}")

    if args.fail_on_source_unavailable and result.source_status == SOURCE_TEMPORARILY_UNAVAILABLE:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
