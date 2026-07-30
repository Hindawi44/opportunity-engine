#!/usr/bin/env python3
"""Enrich one manually selected clothing bankruptcy lead with estate-manager data."""
from __future__ import annotations

import argparse
from pathlib import Path

from opportunity_engine.discovery.estate_manager_enrichment_pilot import (
    EstateManagerEnrichmentCollector,
    write_estate_manager_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--estate-orgnr", required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/estate-manager-enrichment"),
    )
    args = parser.parse_args()

    enrichment = EstateManagerEnrichmentCollector(
        estate_orgnr=args.estate_orgnr,
    ).collect()
    paths = write_estate_manager_artifacts(enrichment, args.output_dir)
    payload = enrichment.to_dict()

    print(f"Estate: {enrichment.estate_name} ({enrichment.estate_orgnr})")
    print(f"Debtor: {enrichment.debtor_name} ({enrichment.debtor_orgnr})")
    print(f"Estate manager identified: {payload['estate_manager_identified']}")
    print(f"Lead stage: {payload['lead_stage']}")
    print("Public sale found: false")
    print("Verified inventory sale: false")
    print("Commercial Top 5 count: 0")
    print("Automatic contact/bid/purchase/payment: false")
    for label, path in paths.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
