#!/usr/bin/env python3
"""Run one live Clothing Inventory scan without manufacturing a candidate.

When an active Auksjonen clothing listing exists, this runner delegates to the
merged single-case end-to-end path. Verified empty/listing results preserve the
existing no-candidate behavior. An unverified zero parse is reported explicitly
instead of being mistaken for evidence that the source is empty.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
for import_root in (REPOSITORY_ROOT, REPOSITORY_ROOT / "src"):
    import_root_text = str(import_root)
    if import_root_text not in sys.path:
        sys.path.insert(0, import_root_text)

from opportunity_engine.source_ingestion.auksjonen import (  # noqa: E402
    AUKSJONEN_CATEGORY_URL,
    PublicPageResponse,
    RawListing,
    fetch_public_page_response,
    inspect_public_page,
)
from scripts.run_clothing_inventory_single_case import (  # noqa: E402
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
    final_url: str | None = None,
    http_status: int | None = None,
    content_type: str | None = None,
    response_byte_count: int | None = None,
) -> dict[str, Any]:
    """Return an end-to-end report or a truthful non-candidate source result."""
    timestamp = _observed_at(observed_at)
    extraction = inspect_public_page(
        html,
        category_url=source_url,
        requested_url=source_url,
        final_url=final_url,
        http_status=http_status,
        content_type=content_type,
        response_byte_count=response_byte_count,
    )
    listings = list(extraction.listings)
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
        report["source_extraction_status"] = extraction.source_extraction_status
        report["source_diagnostics"] = extraction.diagnostics
        return report

    common = {
        "schema_version": "live-clothing-inventory-scan-v1",
        "domain": "CLOTHING_INVENTORY",
        "execution_mode": "LIVE_SOURCE",
        "source_page": source_url,
        "scan_observed_at": timestamp,
        "final_decision": "NO_DECISION",
        "source_extraction_status": extraction.source_extraction_status,
        "source_diagnostics": extraction.diagnostics,
        "live_listings_extracted": len(listings),
        "clothing_listings_extracted": len(clothing),
        "active_clothing_listings": 0,
        "analysis_invoked": False,
        "decision_invoked": False,
        "requires_human_approval": False,
        "automatic_purchase_decision": False,
        "automatic_bid": False,
        "automatic_contact": False,
        "automatic_payment": False,
    }

    if extraction.source_extraction_status == "UNVERIFIED_ZERO":
        return {
            **common,
            "scan_outcome": "SOURCE_EXTRACTION_UNVERIFIED",
            "final_outcome": "SOURCE_EXTRACTION_UNVERIFIED",
            "reason": (
                "The public Auksjonen response produced zero parsed listings "
                "without an explicit empty-category marker."
            ),
            "ended_clothing_listings": 0,
            "ended_clothing_candidates": [],
        }

    ended = [listing for listing in clothing if listing.listing_status == "ENDED"]
    return {
        **common,
        "scan_outcome": "NO_ACTIVE_CANDIDATE",
        "final_outcome": "NO_ACTIVE_CANDIDATE",
        "reason": "No active clothing-related Auksjonen listing was found.",
        "ended_clothing_listings": len(ended),
        "ended_clothing_candidates": [_listing_payload(item) for item in ended],
    }


def build_scan_summary(report: dict[str, Any]) -> str:
    """Create a concise operator summary for a live scan."""
    outcome = report.get("scan_outcome")
    if outcome == "ACTIVE_CANDIDATE_SELECTED":
        decision = report.get("final_decision", "unknown")
        return (
            "Clothing Inventory — Live Scan Result\n"
            "Scan outcome: ACTIVE_CANDIDATE_SELECTED\n"
            f"Source extraction: {report.get('source_extraction_status', 'unknown')}\n"
            f"Final outcome: {report.get('final_outcome', 'unknown')}\n"
            f"Final decision: {decision}\n"
            f"Selected listing: {report.get('selected_listing_id', 'unknown')}\n"
            "Automatic purchase/bid/contact/payment: false\n"
        )

    diagnostics = report.get("source_diagnostics") or {}
    return (
        "Clothing Inventory — Live Scan Result\n"
        f"Scan outcome: {outcome or 'unknown'}\n"
        f"Source extraction: {report.get('source_extraction_status', 'unknown')}\n"
        f"Source: {report.get('source_page', 'unknown')}\n"
        f"Final URL: {diagnostics.get('final_url', 'unknown')}\n"
        f"HTTP status: {diagnostics.get('http_status', 'unknown')}\n"
        f"Response bytes: {diagnostics.get('response_byte_count', 'unknown')}\n"
        f"Anchor tags: {diagnostics.get('anchor_count', 'unknown')}\n"
        f"Listings extracted: {report.get('live_listings_extracted', 0)}\n"
        f"Clothing listings extracted: {report.get('clothing_listings_extracted', 0)}\n"
        f"Ended clothing listings: {report.get('ended_clothing_listings', 0)}\n"
        "Analysis invoked: false\n"
        "Decision invoked: false\n"
        "Automatic purchase/bid/contact/payment: false\n"
    )


def write_scan_outputs(report: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    """Write the canonical case outputs or the non-candidate scan outputs."""
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


def _fixture_response(path: Path, source_url: str) -> PublicPageResponse:
    html = path.read_text(encoding="utf-8")
    return PublicPageResponse(
        html=html,
        requested_url=source_url,
        final_url=source_url,
        http_status=200,
        content_type="text/html; charset=utf-8",
        response_byte_count=len(html.encode("utf-8")),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan Auksjonen for one active Clothing Inventory candidate."
    )
    parser.add_argument("--source-url", default=AUKSJONEN_CATEGORY_URL)
    parser.add_argument("--html-file", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--observed-at")
    args = parser.parse_args()

    response = (
        _fixture_response(args.html_file, args.source_url)
        if args.html_file
        else fetch_public_page_response(args.source_url)
    )
    report = build_live_scan_report(
        html=response.html,
        source_url=args.source_url,
        observed_at=args.observed_at,
        final_url=response.final_url,
        http_status=response.http_status,
        content_type=response.content_type,
        response_byte_count=response.response_byte_count,
    )
    paths = write_scan_outputs(report, args.output_dir)
    for label, path in paths.items():
        print(f"{label}: {path}")
    print(f"scan_outcome: {report['scan_outcome']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
