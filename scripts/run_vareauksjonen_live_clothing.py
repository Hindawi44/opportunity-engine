#!/usr/bin/env python3
"""Run the bounded public Vareauksjonen clothing inventory adapter."""
from __future__ import annotations

import argparse
from pathlib import Path

from opportunity_engine.discovery.vareauksjonen_public_adapter import (
    MAX_CANDIDATE_DETAILS,
    VareauksjonenPublicCollector,
    write_vareauksjonen_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/vareauksjonen-live-clothing"),
    )
    parser.add_argument(
        "--max-candidate-details",
        type=int,
        default=MAX_CANDIDATE_DETAILS,
    )
    args = parser.parse_args()

    collection = VareauksjonenPublicCollector(
        max_candidate_details=args.max_candidate_details,
    ).collect()
    paths = write_vareauksjonen_artifacts(collection, args.output_dir)

    print(f"Public pages read: {len(collection.page_diagnostics)}")
    print(f"Crawl delay respected: {collection.crawl_delay_seconds:g} seconds")
    print(f"Browse candidates: {len(collection.candidates)}")
    print(f"Candidate detail pages read: {len(collection.listings)}")
    print(f"Valid inventory opportunities: {len(collection.inventory_opportunities)}")
    print(f"Individual clothing items excluded: {len(collection.individual_clothing_items)}")
    print(f"Commercial Top 5 count: {min(5, len(collection.inventory_opportunities))}")
    print(f"Scan complete: {collection.scan_complete}")
    print(f"Errors: {len(collection.errors)}")
    print("Paid Brave/OpenAI calls: 0")
    for label, path in paths.items():
        print(f"{label}: {path}")

    # Empty Top 5 is a valid market result. Fail only when the bounded source
    # read was incomplete or one of the required public pages failed.
    return 0 if collection.scan_complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
