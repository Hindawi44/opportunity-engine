#!/usr/bin/env python3
"""Run the authorized, bounded FINN Playwright Clothing Inventory pilot."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from opportunity_engine.discovery.finn_playwright_pilot import (
    DEFAULT_FINN_SEARCH_URL,
    FinnPlaywrightPilotAdapter,
    FinnPlaywrightPilotConfig,
    run_finn_playwright_pilot,
    write_finn_playwright_pilot_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="artifacts/finn-playwright-clothing-pilot",
    )
    parser.add_argument(
        "--search-url",
        action="append",
        dest="search_urls",
        help="Authorized public FINN Torget search URL; may be repeated",
    )
    parser.add_argument("--max-listings", type=int, default=20)
    parser.add_argument("--max-search-pages", type=int, default=1)
    parser.add_argument("--delay-seconds", type=float, default=3.0)
    parser.add_argument("--navigation-timeout-seconds", type=float, default=30.0)
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Show Chromium instead of running headless",
    )
    args = parser.parse_args()

    permission_reference = os.environ.get(
        "FINN_WRITTEN_AUTOMATION_PERMISSION_REF",
        "",
    ).strip()
    if not permission_reference:
        raise SystemExit(
            "FINN_WRITTEN_AUTOMATION_PERMISSION_REF is required. "
            "Do not run this pilot without explicit written permission from FINN."
        )

    config = FinnPlaywrightPilotConfig(
        written_permission_reference=permission_reference,
        search_urls=tuple(args.search_urls or (DEFAULT_FINN_SEARCH_URL,)),
        max_listings=args.max_listings,
        max_search_pages=args.max_search_pages,
        delay_seconds=args.delay_seconds,
        navigation_timeout_seconds=args.navigation_timeout_seconds,
        headless=not args.headful,
    )
    collection = FinnPlaywrightPilotAdapter(config).collect()
    result = run_finn_playwright_pilot(collection)
    paths = write_finn_playwright_pilot_artifacts(
        result,
        collection,
        Path(args.output_dir),
    )
    report = result["search_run_report"]
    print(f"Execution status: {report['execution_status']}")
    print(f"Opportunity quality: {report['opportunity_quality_status']}")
    print(f"Collected listings: {report['network_listings_collected']}")
    print(f"Top opportunities: {report['top5_count']}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
