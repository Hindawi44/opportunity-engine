#!/usr/bin/env python3
"""Collect live Auksjonen clothing items and promote inventory lots only."""
from __future__ import annotations

import argparse
from pathlib import Path

from opportunity_engine.discovery.auksjonen_public_api_adapter import (
    AuksjonenPublicApiCollector,
    write_live_clothing_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="artifacts/auksjonen-live-clothing",
    )
    parser.add_argument("--max-listings", type=int, default=10)
    args = parser.parse_args()

    collection = AuksjonenPublicApiCollector(
        max_listings=args.max_listings,
    ).collect()
    paths = write_live_clothing_artifacts(collection, Path(args.output_dir))

    opportunities = collection.inventory_opportunities
    individuals = collection.individual_clothing_items
    print(f"Reported category size: {collection.reported_size}")
    print(f"Items received: {collection.items_received}")
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

    # An empty Top 5 is a valid commercial result when the source was read
    # successfully. Fail only when the live source adapter recorded errors.
    return 0 if not collection.errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
