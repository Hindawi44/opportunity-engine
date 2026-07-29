#!/usr/bin/env python3
"""Run the current-only Auksjoner.no clothing inventory adapter."""
from __future__ import annotations

import argparse
from pathlib import Path

from opportunity_engine.discovery.auksjoner_no_public_adapter import (
    MAX_AUCTIONS,
    AuksjonerNoPublicCollector,
    write_auksjoner_no_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/auksjoner-no-live-clothing"),
    )
    parser.add_argument("--max-auctions", type=int, default=MAX_AUCTIONS)
    args = parser.parse_args()

    collection = AuksjonerNoPublicCollector(max_auctions=args.max_auctions).collect()
    paths = write_auksjoner_no_artifacts(collection, args.output_dir)

    print(f"Current auctions received: {collection.items_received}")
    print(f"Crawl delay respected: {collection.crawl_delay_seconds:g} seconds")
    print(f"Valid inventory opportunities: {len(collection.inventory_opportunities)}")
    print(
        "Clothing auctions without lot evidence excluded: "
        f"{len(collection.clothing_non_lots)}"
    )
    print(f"Commercial Top 5 count: {min(5, len(collection.inventory_opportunities))}")
    print(f"Scan complete: {collection.scan_complete}")
    print(f"Errors: {len(collection.errors)}")
    print("Past auction page queried: false")
    print("Paid Brave/OpenAI calls: 0")
    for label, path in paths.items():
        print(f"{label}: {path}")

    return 0 if collection.scan_complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
