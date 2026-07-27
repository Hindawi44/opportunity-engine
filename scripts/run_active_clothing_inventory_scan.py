#!/usr/bin/env python3
"""Run one live Clothing Inventory scan without manufacturing a candidate.

When an active Auksjonen clothing listing exists, this runner delegates to the
merged single-case end-to-end path. When the public page contains no active
clothing listing, it records a deterministic ``NO_ACTIVE_CANDIDATE`` scan result
instead of raising an operational error or promoting an ended listing.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opportunity_engine.source_ingestion.auksjonen import (
    AUKSJONEN_CATEGORY_URL,
    RawListing,
    fetch_public_page,
    parse_public_listings,
)
from scripts.run_clothing_inventory_single_case import (
    build_live_final_report,
    is_active_listing,
    is_clothing_listing,
    write_report_outputs,
)

DEFAULT_OUTPUT_DIR = Path("data/validation/active-clothing-inventory-scan")


def _observed_at(value: str | None) -> str:
    return value or datetime.now(timezone.utc).isoformat()


def _listing_payload(listing: RawListing) -> dict[str, Any]:
    return {
        "listing_id": listing.listing_id,
        "title": listing.title,
        "url": listing.url,
        "asking_price_nok": listing.asking_price_nok,
        "location": listing.location,
        "listing_status": listing.listing_status,
    }


def build_live_scan_report(
    *,
    html: str,
    source_url: str = AUKSJONEN_CATEGORY_URL,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Return an end-to-end report or an honest no-active-candidate result."""
    timestamp = _observed_at(observed_at)
    listings = parse_public_listings(html, category_url=source_url)
    clothing = [listing for listing in listings if is_clothing_listing(listing)]
    active = [listing for listing in clothing if is_active_listing(listing)]

    if active:
        report = build_live_final_report(
            html=html,
            source_url=source_url,
            observed_at=timestamp,
        )
        report["scan_outcome"] = "ACTIVE_CANDIDATE_SELECTED"
        report["scan_observed_at"] = timestamp
        return report

    ended = [listing for listing in clothing if listing.listing_status == "ENDED"]
    return {
        "schema_version": "live-clothing-inventory-scan-v1",
        "domain": "CLOTHING_INVENTORY",
        "execution_mode": "LIVE_SOURCE",
        "source_page": source_url,
        "scan_observed_at": timestamp,
        "scan_outcome": "NO_ACTIVE_CANDIDATE",
        "final_outcome": "NO_ACTIVE_CANDIDATE",
        "final_decision": "NO_DECISION",
        "reason": "No active clothing-related Auksjonen listing was found.",
        "live_listings_extracted": len(listings),
        "clothing_listings_extracted": len(clothing),
        "active_clothing_listings": 0,
        "ended_clothing_listings": len(ended),
        "ended_clothing_candidates": [_listing_payload(item) for item in ended],
        "analysis_invoked": False,
        "decision_invoked": False,
        "requires_human_approval": False,
        "automatic_purchase_decision": False,
        "automatic_bid": False,
        "automatic_contact": False,
        "automatic_payment": False,
    }


def build_scan_summary(report: dict[str, Any]) -> str:
    """Create a concise operator summary for a live scan."""
    if report.get("scan_outcome") == "ACTIVE_CANDIDATE_SELECTED":
        decision = report.get("final_decision", "unknown")
        return (
            "Clothing Inventory — Live Scan Result\n"
            "Scan outcome: ACTIVE_CANDIDATE_SELECTED\n"
            f"Final outcome: {report.get('final_outcome', 'unknown')}\n"
            f"Final decision: {decision}\n"
            f"Selected listing: {report.get('selected_listing_id', 'unknown')}\n"
            "Automatic purchase/bid/contact/payment: false\n"
        )

    return (
        "Clothing Inventory — Live Scan Result\n"
        "Scan outcome: NO_ACTIVE_CANDIDATE\n"
        f"Source: {report.get('source_page', 'unknown')}\n"
        f"Listings extracted: {report.get('live_listings_extracted', 0)}\n"
        f"Clothing listings extracted: {report.get('clothing_listings_extracted', 0)}\n"
        f"Ended clothing listings: {report.get('ended_clothing_listings', 0)}\n"
        "Analysis invoked: false\n"
        "Decision invoked: false\n"
        "Automatic purchase/bid/contact/payment: false\n"
    )


def write_scan_outputs(report: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    """Write the canonical case outputs or the no-candidate scan outputs."""
    if report.get("scan_outcome") == "ACTIVE_CANDIDATE_SELECTED":
        return write_report_outputs(report, output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "scan-report.json"
    summary_path = output_dir / "operator-summary.txt"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(build_scan_summary(report), encoding="utf-8")
    return {"report": report_path, "summary": summary_path}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan Auksjonen for one active Clothing Inventory candidate."
    )
    parser.add_argument("--source-url", default=AUKSJONEN_CATEGORY_URL)
    parser.add_argument("--html-file", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--observed-at")
    args = parser.parse_args()

    html = (
        args.html_file.read_text(encoding="utf-8")
        if args.html_file
        else fetch_public_page(args.source_url)
    )
    report = build_live_scan_report(
        html=html,
        source_url=args.source_url,
        observed_at=args.observed_at,
    )
    paths = write_scan_outputs(report, args.output_dir)
    for label, path in paths.items():
        print(f"{label}: {path}")
    print(f"scan_outcome: {report['scan_outcome']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
