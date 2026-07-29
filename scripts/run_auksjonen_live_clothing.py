#!/usr/bin/env python3
"""Collect bounded live Auksjonen clothing categories and promote inventory lots."""
from __future__ import annotations

import argparse
from pathlib import Path

from opportunity_engine.discovery.auksjonen_multi_category_adapter import (
    AuksjonenMultiCategoryCollector,
    write_multi_category_artifact,
)
from opportunity_engine.discovery.auksjonen_public_api_adapter import (
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

    result = AuksjonenMultiCategoryCollector(
        max_listings=args.max_listings,
        page_size=args.page_size,
        max_pages=args.max_pages,
    ).collect()
    collection = result.combined
    paths = write_live_clothing_artifacts(collection, Path(args.output_dir))
    paths["category_scans"] = write_multi_category_artifact(
        result,
        Path(args.output_dir),
    )

    opportunities = collection.inventory_opportunities
    individuals = collection.individual_clothing_items
    print(f"Categories scanned: {len(result.scans)}")
    for scan in result.scans:
        print(
            f"- {scan.category.label} ({scan.category.category_id}): "
            f"reported={scan.reported_size}, pages={scan.pages_fetched}, "
            f"items={scan.items_received}, complete={scan.scan_complete}"
        )
    print(f"Combined reported size: {collection.reported_size}")
    print(f"Pages fetched across categories: {collection.pages_fetched}")
    print(f"Items received across categories: {collection.items_received}")
    print(f"Full multi-category scan complete: {result.scan_complete}")
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

    # An empty Top 5 is valid when every approved category was read completely.
    return 0 if result.scan_complete and not collection.errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
