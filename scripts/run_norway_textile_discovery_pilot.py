#!/usr/bin/env python3
"""Run the bounded Norway textile and sewing discovery pilot."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.live_search import run_live_discovery
from opportunity_engine.discovery.query_builder import build_clothing_inventory_queries
from scripts.run_discovery_v12_live_pilot import (
    build_mobile_report,
    write_github_step_summary,
    write_reports,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        default="artifacts/norway-textile-discovery-report.json",
    )
    parser.add_argument(
        "--text-report",
        default="artifacts/norway-textile-discovery-phone-report.txt",
    )
    parser.add_argument("--results-per-query", type=int, default=10)
    parser.add_argument("--mobile-limit", type=int, default=10)
    parser.add_argument("--query-delay-seconds", type=float, default=1.1)
    args = parser.parse_args()

    if not 1 <= args.results_per_query <= 20:
        raise SystemExit("--results-per-query must be between 1 and 20")
    if args.query_delay_seconds < 0:
        raise SystemExit("--query-delay-seconds must not be negative")

    api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("BRAVE_SEARCH_API_KEY is required")

    query_records = build_clothing_inventory_queries(country="Norge")
    queries = [record["query"] for record in query_records]
    report = run_live_discovery(
        queries,
        BraveSearchProvider(api_key=api_key),
        results_per_query=args.results_per_query,
        query_delay_seconds=args.query_delay_seconds,
        apply_result_filter=True,
        apply_quality_engine=True,
    )
    report.update(
        {
            "pilot_version": "norway-textile-keyword-pack-v1",
            "pilot_topic": "TEXTILE_AND_SEWING",
            "market_code": "NO",
            "query_records": query_records,
            "live_network_used": True,
            "automatic_page_open": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }
    )

    mobile_report = build_mobile_report(report, limit=max(1, args.mobile_limit))
    write_reports(
        report,
        mobile_report,
        json_path=Path(args.report),
        text_path=Path(args.text_report),
    )
    print(mobile_report)
    print(json.dumps(
        {
            "category_counts": {
                category: sum(
                    item.get("category") == category
                    for item in report["classified_results"]
                )
                for category in sorted({
                    item.get("category")
                    for item in report["classified_results"]
                    if item.get("category")
                })
            },
            "report": args.report,
            "text_report": args.text_report,
        },
        ensure_ascii=False,
    ))
    write_github_step_summary(mobile_report)
    return 0 if report["status"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
