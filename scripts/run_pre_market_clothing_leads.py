#!/usr/bin/env python3
"""Rank recent clothing bankruptcy leads for pre-market human review."""
from __future__ import annotations

import argparse
from pathlib import Path

from opportunity_engine.discovery.konkurs_app_clothing_adapter import (
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_PAGE_SIZE,
    KonkursAppClothingCollector,
)
from opportunity_engine.discovery.pre_market_clothing_leads import (
    DEFAULT_REVIEW_LIMIT,
    MAX_REVIEW_LIMIT,
    build_pre_market_pilot,
    write_pre_market_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/pre-market-clothing-leads"),
    )
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument(
        "--review-limit",
        type=int,
        choices=range(1, MAX_REVIEW_LIMIT + 1),
        default=DEFAULT_REVIEW_LIMIT,
    )
    args = parser.parse_args()

    source_collection = KonkursAppClothingCollector(
        lookback_days=args.lookback_days,
        page_size=args.page_size,
    ).collect()
    pilot = build_pre_market_pilot(
        source_collection,
        review_limit=args.review_limit,
    )
    paths = write_pre_market_artifacts(pilot, args.output_dir)

    print(f"Lookback from: {pilot.source_from_date}")
    print(f"Items received: {pilot.items_received}")
    print(f"Pre-market leads ranked: {len(pilot.leads)}")
    print(f"Review queue count: {len(pilot.review_top)}")
    print("Verified inventory sales: 0")
    print("Commercial Top 5 count: 0")
    print(f"Scan complete: {pilot.scan_complete}")
    print(f"Errors: {len(pilot.errors)}")
    print("Score is verified inventory probability: false")
    print("Paid Brave/OpenAI calls: 0")
    print("Automatic contact/bid/purchase/payment: false")
    if pilot.review_top:
        first = pilot.review_top[0]
        print(f"First review lead: {first.source_lead.debtor_name}")
        print(f"First signal score: {first.inventory_signal_score}")
        print(f"First lead URL: {first.source_lead.url}")
    for label, path in paths.items():
        print(f"{label}: {path}")

    return 0 if pilot.scan_complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
