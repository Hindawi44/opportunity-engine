#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from opportunity_engine.discovery.netherlands_market_discovery import (
    collect_netherlands_market_signals,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run bounded Netherlands clothing/bridal liquidation discovery."
    )
    parser.add_argument(
        "--output",
        default="artifacts/netherlands-market-discovery.json",
        help="JSON output path",
    )
    parser.add_argument("--query-budget", type=int, default=None)
    parser.add_argument("--results-per-query", type=int, default=10)
    args = parser.parse_args()

    kwargs = {
        "environment": os.environ,
        "results_per_query": args.results_per_query,
    }
    if args.query_budget is not None:
        kwargs["query_budget"] = args.query_budget

    report = collect_netherlands_market_signals(**kwargs)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report.get("status"),
                "queries_attempted": report.get("queries_attempted"),
                "queries_succeeded": report.get("queries_succeeded"),
                "accepted_signal_count": report.get("accepted_signal_count"),
                "independent_domain_count": report.get("independent_domain_count"),
                "output": output.as_posix(),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report.get("status") not in {"BLOCKED_RETRIEVAL"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
