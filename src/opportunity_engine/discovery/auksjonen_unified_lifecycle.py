"""Canonical lifecycle output for bounded Auksjonen clothing inventory lots.

The public collector remains authoritative for discovery and Top 5 ordering. This
module only maps its active inventory-lot records into the existing unified report
contract so they can use the shared SQLite lifecycle persistence path.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from .auksjonen_public_api_adapter import (
    AuksjonenLiveClothingCollection,
    AuksjonenLiveClothingListing,
)
from .unified_opportunity_report import (
    build_unified_opportunity_report,
    serialize_unified_opportunity_report,
)

AUKSJONEN_ANALYSIS_BLOCKERS = (
    "verified exact item-page evidence",
    "verified quantity and condition",
    "documented final payable price including auction fees and VAT",
    "domestic pickup or delivery logistics basis",
    "documented resale-market evidence",
)


def _location(listing: AuksjonenLiveClothingListing) -> str | None:
    parts = [listing.address, listing.zip_code, listing.city]
    values = [str(value).strip() for value in parts if str(value or "").strip()]
    return ", ".join(dict.fromkeys(values)) or None


def auksjonen_listing_to_discovery_candidate(
    listing: AuksjonenLiveClothingListing,
    *,
    top5_eligible: bool,
) -> dict[str, Any]:
    """Map one source-native inventory lot without estimating missing facts."""
    if not listing.inventory_lot_signal:
        raise ValueError("only explicit Auksjonen inventory lots may be unified")
    if listing.listing_status != "ACTIVE":
        raise ValueError("only active Auksjonen inventory lots may be unified")

    return {
        "title": listing.title,
        "scenario": "WAREHOUSE_SURPLUS",
        "opportunity_state": "STRONG_LEAD_REQUIRES_VERIFICATION",
        "reason": (
            "active public API clothing-inventory lot; exact item page and "
            "commercial evidence still require human verification"
        ),
        "page_role": "ITEM_LISTING",
        "opportunity_identity": listing.url,
        "identity_stable": True,
        "listing_status": listing.listing_status,
        "top5_eligible": bool(top5_eligible),
        "analysis_eligible": False,
        "verified": False,
        "source_urls": [listing.url],
        "source_providers": ["Auksjonen.no"],
        "textile_category": "CLOTHING_INVENTORY",
        "inventory_type": "clothing_inventory_lot",
        "location": _location(listing),
        "source_object_id": str(listing.object_id),
        "auction_occurrence_id": (
            f"auksjonen-auction:{listing.auction_id}:object:{listing.object_id}"
        ),
        "evidence_signals": [
            "active_public_api_listing",
            "explicit_inventory_lot_signal",
        ],
        "verification": [
            {
                "url": listing.url,
                "title": listing.title,
                "bounded_context": (
                    "The bounded public category API reports an active clothing "
                    "listing with an explicit multi-item lot signal."
                ),
                "page_role": "PUBLIC_API_LISTING",
                "listing_status": listing.listing_status,
                "verified": False,
            }
        ],
        "missing_information": list(AUKSJONEN_ANALYSIS_BLOCKERS),
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def build_auksjonen_discovery_result(
    collection: AuksjonenLiveClothingCollection,
) -> dict[str, Any]:
    """Return the minimum discovery envelope used by the unified report builder."""
    opportunities = collection.inventory_opportunities
    candidates = [
        auksjonen_listing_to_discovery_candidate(
            listing,
            top5_eligible=index < 5,
        )
        for index, listing in enumerate(opportunities)
    ]
    return {
        "all_discovered_candidates": candidates,
        "discovery_top5": candidates[:5],
    }


def build_auksjonen_unified_report(
    collection: AuksjonenLiveClothingCollection,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build source candidates and their canonical lifecycle report."""
    result = build_auksjonen_discovery_result(collection)
    generated_at = datetime.fromisoformat(collection.captured_at.replace("Z", "+00:00"))
    report = build_unified_opportunity_report(
        result,
        generated_at=generated_at,
        market_code="NO",
        currency="NOK",
        domain="CLOTHING_INVENTORY",
    )
    return result, report


def write_auksjonen_unified_artifacts(
    collection: AuksjonenLiveClothingCollection,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Write audit candidates and the canonical report beside source artifacts."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    result, report = build_auksjonen_unified_report(collection)

    candidates_path = destination / "all-discovered-candidates.json"
    unified_path = destination / "unified-opportunity-report.json"
    candidates_path.write_text(
        json.dumps(
            result["all_discovered_candidates"],
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    unified_path.write_text(
        serialize_unified_opportunity_report(report) + "\n",
        encoding="utf-8",
    )
    return {
        "all_discovered_candidates": candidates_path,
        "unified_opportunity_report": unified_path,
    }
