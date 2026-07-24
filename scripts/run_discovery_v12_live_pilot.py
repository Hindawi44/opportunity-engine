#!/usr/bin/env python3
"""Run the first live Discovery Engine pilot against Brave Search."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.live_search import run_live_discovery
from opportunity_engine.discovery.query_builder import build_clothing_inventory_queries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="artifacts/discovery-v1.2-live-pilot-summary.json")
    parser.add_argument("--country", default="Norge")
    parser.add_argument("--results-per-query", type=int, default=10)
    args = parser.parse_args()

    api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("BRAVE_SEARCH_API_KEY is required")

    query_records = build_clothing_inventory_queries(country=args.country)
    queries = [item["query"] for item in query_records]
    provider = BraveSearchProvider(api_key=api_key)
    report = run_live_discovery(
        queries,
        provider,
        results_per_query=args.results_per_query,
    )
    report["pilot_version"] = "1.2"
    report["pilot_topic"] = "CLOTHING_INVENTORY"
    report["query_records"] = query_records
    report["live_network_used"] = True
    report["automatic_purchase_decision"] = False

    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
