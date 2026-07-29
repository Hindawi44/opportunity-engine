#!/usr/bin/env python3
"""Collect active clothing listings from the discovered public Auksjonen API."""
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

    print(f"Reported category size: {collection.reported_size}")
    print(f"Items received: {collection.items_received}")
    print(f"Active clothing listings: {len(collection.listings)}")
    print(f"Errors: {len(collection.errors)}")
    print("Paid Brave/OpenAI calls: 0")
    if collection.listings:
        first = collection.listings[0]
        print(f"First listing: {first.title}")
        print(f"First URL: {first.url}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0 if collection.listings else 2


if __name__ == "__main__":
    raise SystemExit(main())
