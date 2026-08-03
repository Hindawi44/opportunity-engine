"""Canonical lifecycle output for bounded Auksjonen clothing inventory lots.

The public collector remains authoritative for discovery and Top 5 ordering. This
module only maps its active inventory-lot records into the existing unified report
contract so they can use the shared SQLite lifecycle persistence path.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

from .auksjonen_public_api_adapter import (
    AuksjonenLiveClothingCollection,
    AuksjonenLiveClothingListing,
)
from .unified_opportunity_report import (
    build_unified_opportunity_report,
    serialize_unified_opportunity_report,
)

# Only facts required to trust the source-native listing belong in the lifecycle
# verification gate. Commercial calculations are deliberately deferred to the
# one-opportunity analysis dossier and must not masquerade as source blockers.
AUKSJONEN_REQUIRED_VERIFICATION = (
    "verified exact item-page evidence",
)
AUKSJONEN_ANALYSIS_TASKS = (
    "confirm quantity and condition from the exact item page",
    "calculate final payable price including auction fees and VAT",
    "calculate domestic pickup or delivery logistics",
    "document resale-market evidence",
)

_QUANTITY_PATTERN = re.compile(
    r"\b(?P<quantity>\d+)\s*(?:stk|plagg|jakker|bukser|kjoler|skjorter|"
    r"gensere|sko|varer)\b",
    re.I,
)


def _location(listing: AuksjonenLiveClothingListing) -> str | None:
    parts = [listing.address, listing.zip_code, listing.city]
    values = [str(value).strip() for value in parts if str(value or "").strip()]
    return ", ".join(dict.fromkeys(values)) or None


def _explicit_quantity(title: str) -> int | None:
    """Return a title-native quantity only when it is explicitly stated."""
    match = _QUANTITY_PATTERN.search(str(title or ""))
    if match is None:
        return None
    quantity = int(match.group("quantity"))
    return quantity if quantity > 0 else None


def _current_price(listing: AuksjonenLiveClothingListing) -> tuple[float | None, str | None]:
    """Return one source-native current price without estimating final payable cost."""
    if listing.current_bid_nok is not None:
        return float(listing.current_bid_nok), "CURRENT_BID"
    if listing.buy_now_price_nok is not None:
        return float(listing.buy_now_price_nok), "BUY_NOW"
    if listing.start_price_nok is not None:
        return float(listing.start_price_nok), "START_PRICE"
    return None, None


def _verification_blockers(listing: AuksjonenLiveClothingListing) -> list[str]:
    """Return only missing source facts that block trusted analysis entry."""
    blockers = list(AUKSJONEN_REQUIRED_VERIFICATION)
    price, _ = _current_price(listing)
    if price is None:
        blockers.append("current bid, buy-now price, or start price")
    if _location(listing) is None:
        blockers.append("pickup location")
    return blockers


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

    price_nok, price_kind = _current_price(listing)
    blockers = _verification_blockers(listing)

    return {
        "title": listing.title,
        "scenario": "WAREHOUSE_SURPLUS",
        "opportunity_state": "STRONG_LEAD_REQUIRES_VERIFICATION",
        "reason": (
            "active public API clothing-inventory lot; exact item-page verification "
            "is the remaining lifecycle gate, while fees, logistics, condition, and "
            "resale evidence are downstream analysis tasks"
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
        "quantity": _explicit_quantity(listing.title),
        "price_nok": price_nok,
        "price_kind": price_kind,
        "current_bid_nok": listing.current_bid_nok,
        "buy_now_price_nok": listing.buy_now_price_nok,
        "start_price_nok": listing.start_price_nok,
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
        "verification_blockers": blockers,
        "analysis_tasks": list(AUKSJONEN_ANALYSIS_TASKS),
        "missing_information": blockers,
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
