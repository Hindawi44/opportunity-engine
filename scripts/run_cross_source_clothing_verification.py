#!/usr/bin/env python3
"""Run the bounded Konkurs.app-to-Auksjonen clothing sale verifier."""
from __future__ import annotations

import argparse
from pathlib import Path

from opportunity_engine.discovery.cross_source_clothing_sale_verifier import (
    CrossSourceClothingSaleVerifier,
    write_cross_source_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/cross-source-clothing-verification"),
    )
    parser.add_argument("--lookback-days", type=int, default=365)
    parser.add_argument("--max-bankruptcy-leads", type=int, default=100)
    parser.add_argument("--max-detail-pages", type=int, default=5)
    args = parser.parse_args()

    result = CrossSourceClothingSaleVerifier(
        lookback_days=args.lookback_days,
        max_bankruptcy_leads=args.max_bankruptcy_leads,
        max_detail_pages=args.max_detail_pages,
    ).collect()
    paths = write_cross_source_artifacts(result, args.output_dir)

    print(f"Konkurs.app API requests: {result.bankruptcy_requests}")
    print(f"Bankruptcy records received: {result.bankruptcy_items_received}")
    print(f"Bankruptcy leads retained: {len(result.bankruptcy_leads)}")
    print(f"Auksjonen categories scanned: {len(result.auksjonen_result.scans)}")
    print(f"Active inventory lots checked: {len(result.records)}")
    print(f"Detail pages requested: {result.detail_pages_requested}")
    print(f"Review leads: {len(result.review_leads)}")
    print(f"Verified inventory sales: {len(result.verified_sales)}")
    print(f"Commercial Top 5 count: {min(5, len(result.verified_sales))}")
    print(f"Scan complete: {result.scan_complete}")
    print(f"Errors: {len(result.errors)}")
    print("Paid Brave/OpenAI calls: 0")
    for label, path in paths.items():
        print(f"{label}: {path}")

    # A truthful empty commercial Top 5 is a successful scan. Fail only when a
    # required bounded source read failed or the Auksjonen scan was incomplete.
    return 0 if result.scan_complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
