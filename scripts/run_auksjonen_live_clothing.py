#!/usr/bin/env python3
"""Collect all bounded live Auksjonen clothing pages and promote inventory lots only."""
from __future__ import annotations

import argparse
from pathlib import Path

from opportunity_engine.discovery.auksjonen_public_api_adapter import (
    AuksjonenPublicApiCollector,
    DEFAULT_PAGE_SIZE,
    MAX_LISTINGS,
    MAX_PAGES,
    write_live_clothing_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="artifacts/auksjonen-live-clothing",
    )
    parser.add_argument("--max-listings", type=int, default=MAX_LISTINGS)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES)
    args = parser.parse_args()

    collection = AuksjonenPublicApiCollector(
        max_listings=args.max_listings,
        page_size=args.page_size,
        max_pages=args.max_pages,
    ).collect()
    paths = write_live_clothing_artifacts(collection, Path(args.output_dir))

    opportunities = collection.inventory_opportunities
    individuals = collection.individual_clothing_items
    print(f"Reported category size: {collection.reported_size}")
    print(f"Pages fetched: {collection.pages_fetched}")
    print(f"Items received across all pages: {collection.items_received}")
    print(f"Full bounded scan complete: {collection.scan_complete}")
    print(f"Active clothing items: {len(collection.listings)}")
    print(f"Valid inventory opportunities: {len(opportunities)}")
    print(f"Individual clothing items excluded from Top 5: {len(individuals)}")
    print(f"Errors: {len(collection.errors)}")
    print("Paid Brave/OpenAI calls: 0")
    if opportunities:
        first = opportunities[0]
        print(f"First inventory opportunity: {first.title}")
        print(f"First inventory URL: {first.url}")
    else:
        print("No valid inventory-lot opportunities found.")
    for name, path in paths.items():
        print(f"{name}: {path}")

    # An empty Top 5 is valid when every bounded source page was read.
    # Fail only on source errors or an incomplete bounded scan.
    return 0 if not collection.errors and collection.scan_complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
