#!/usr/bin/env python3
"""Collect recent active clothing bankruptcy leads from Konkurs.app."""
from __future__ import annotations

import argparse
from pathlib import Path

from opportunity_engine.discovery.konkurs_app_clothing_adapter import (
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_PAGE_SIZE,
    KonkursAppClothingCollector,
    write_konkurs_app_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="artifacts/konkurs-app-clothing",
    )
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    args = parser.parse_args()

    collection = KonkursAppClothingCollector(
        lookback_days=args.lookback_days,
        page_size=args.page_size,
    ).collect()
    paths = write_konkurs_app_artifacts(collection, Path(args.output_dir))

    print(f"Lookback from: {collection.from_date}")
    print(f"API requests: {len(collection.endpoints)}")
    print(f"Items received: {collection.items_received}")
    print(f"Clothing bankruptcy leads: {len(collection.leads)}")
    print("Verified inventory sales: 0")
    print("Commercial Top 5 count: 0")
    print(f"Scan complete: {collection.scan_complete}")
    print(f"Errors: {len(collection.errors)}")
    print("Paid Brave/OpenAI calls: 0")
    if collection.leads:
        first = collection.leads[0]
        print(f"First verification lead: {first.debtor_name}")
        print(f"First lead URL: {first.url}")
    for name, path in paths.items():
        print(f"{name}: {path}")

    return 0 if collection.scan_complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
