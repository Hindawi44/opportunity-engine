#!/usr/bin/env python3
"""Search public web results for one estate's sale or liquidation channel."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.estate_manager_enrichment_pilot import (
    EstateManagerEnrichmentCollector,
)
from opportunity_engine.discovery.pre_market_sale_channel_search import (
    DEFAULT_RESULTS_PER_QUERY,
    MAX_RESULTS_PER_QUERY,
    run_sale_channel_search,
    write_sale_channel_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--estate-orgnr", required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/pre-market-sale-channel-search"),
    )
    parser.add_argument(
        "--results-per-query",
        type=int,
        choices=range(1, MAX_RESULTS_PER_QUERY + 1),
        default=DEFAULT_RESULTS_PER_QUERY,
    )
    parser.add_argument(
        "--freshness",
        choices=("none", "pd", "pw", "pm", "py"),
        default="py",
    )
    args = parser.parse_args()

    api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("BRAVE_SEARCH_API_KEY is required")

    enrichment = EstateManagerEnrichmentCollector(
        estate_orgnr=args.estate_orgnr,
    ).collect()
    provider = BraveSearchProvider(
        api_key,
        freshness=None if args.freshness == "none" else args.freshness,
        extra_snippets=True,
        operators=True,
    )
    result = run_sale_channel_search(
        enrichment,
        provider,
        results_per_query=args.results_per_query,
    )
    paths = write_sale_channel_artifacts(result, args.output_dir)

    print(f"Estate: {enrichment.estate_name} ({enrichment.estate_orgnr})")
    print(f"Debtor: {enrichment.debtor_name} ({enrichment.debtor_orgnr})")
    print(f"Queries: {len(result.queries)}")
    print(f"Requests made: {result.requests_made}")
    print(f"Raw hits: {result.raw_hits}")
    print(f"Identity-matched candidates: {len(result.candidates)}")
    print(f"Sale-listing candidates: {len(result.sale_listing_candidates)}")
    print(
        "Liquidation-channel candidates: "
        f"{len(result.liquidation_channel_candidates)}"
    )
    print(f"Scan complete: {result.scan_complete}")
    print(f"Errors: {len(result.errors)}")
    print("Search snippets confirm a sale: false")
    print("Public sale found: false")
    print("Commercial Top 5 count: 0")
    print("Automatic page open/contact/bid/purchase/payment: false")
    for label, path in paths.items():
        print(f"{label}: {path}")

    return 0 if result.scan_complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
