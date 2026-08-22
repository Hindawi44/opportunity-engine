#!/usr/bin/env python3
"""Run the scheduled promoted learned-query Core discovery source."""
from __future__ import annotations

import argparse
import json

from opportunity_engine.promoted_learned_core_discovery import (
    collect_promoted_learned_core_opportunities,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--results-per-query", type=int, default=10)
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--max-terms", type=int, default=1)
    args = parser.parse_args()

    report = collect_promoted_learned_core_opportunities(
        args.output_dir,
        results_per_query=args.results_per_query,
        max_pages=args.max_pages,
        max_terms=args.max_terms,
    )
    print(
        json.dumps(
            {
                "status": report.get("status"),
                "request_count": report.get("request_count", 0),
                "page_request_count": report.get("page_request_count", 0),
                "verified_opportunity_count": report.get("verified_opportunity_count", 0),
                "applied_terms": report.get("applied_terms") or [],
                "automatic_query_activation": report.get("automatic_query_activation", False),
                "automatic_purchase": report.get("automatic_purchase", False),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report.get("status") not in {"BLOCKED_CONFIGURATION"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
