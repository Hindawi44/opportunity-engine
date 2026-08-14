"""Canonical lifecycle output for bounded Auksjonen clothing inventory lots.

The public collector remains authoritative for discovery and Top 5 ordering. This
module maps active inventory lots plus optional exact public item-page evidence
into the existing unified report contract and shared SQLite lifecycle path.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .auksjonen_public_api_adapter import (
    AuksjonenLiveClothingCollection,
    AuksjonenLiveClothingListing,
)
from .unified_opportunity_report import (
    build_unified_opportunity_report,
    serialize_unified_opportunity_report,
)

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
    match = _QUANTITY_PATTERN.search(str(title or ""))
    if match is None:
        return None
    quantity = int(match.group("quantity"))
    return quantity if quantity > 0 else None


def _current_price(listing: AuksjonenLiveClothingListing) -> tuple[float | None, str | None]:
    if listing.current_bid_nok is not None:
        return float(listing.current_bid_nok), "CURRENT_BID"
    if listing.buy_now_price_nok is not None:
        return float(listing.buy_now_price_nok), "BUY_NOW"
    if listing.start_price_nok is not None:
        return float(listing.start_price_nok), "START_PRICE"
    return None, None


def _verified_exact_item(evidence: Mapping[str, Any] | None) -> bool:
    return bool(evidence and evidence.get("exact_item_page_verified") is True)


def _verification_blockers(
    listing: AuksjonenLiveClothingListing,
    evidence: Mapping[str, Any] | None = None,
) -> list[str]:
    blockers: list[str] = []
    if not _verified_exact_item(evidence):
        blockers.extend(AUKSJONEN_REQUIRED_VERIFICATION)
    price, _ = _current_price(listing)
    if price is None:
        blockers.append("current bid, buy-now price, or start price")
    if _location(listing) is None:
        blockers.append("pickup location")
    return blockers


def _observed(evidence: Mapping[str, Any] | None, key: str) -> Any:
    if not evidence:
        return None
    value = evidence.get(key)
    return None if value in (None, "", [], {}) else value


def auksjonen_listing_to_discovery_candidate(
    listing: AuksjonenLiveClothingListing,
    *,
    top5_eligible: bool,
    exact_item_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Map one source-native inventory lot without estimating missing facts."""
    if not listing.inventory_lot_signal:
        raise ValueError("only explicit Auksjonen inventory lots may be unified")
    if listing.listing_status != "ACTIVE":
        raise ValueError("only active Auksjonen inventory lots may be unified")

    price_nok, price_kind = _current_price(listing)
    blockers = _verification_blockers(listing, exact_item_evidence)
    verified = _verified_exact_item(exact_item_evidence)
    analysis_eligible = not blockers
    quantity = _observed(exact_item_evidence, "quantity")
    if quantity is None:
        quantity = _explicit_quantity(listing.title)

    evidence_signals = ["active_public_api_listing", "explicit_inventory_lot_signal"]
    if verified:
        evidence_signals.append("verified_exact_public_item_page")

    verification_row: dict[str, Any] = {
        "url": listing.url,
        "title": _observed(exact_item_evidence, "title") or listing.title,
        "bounded_context": (
            "The bounded public category API reports an active clothing listing "
            "with an explicit multi-item lot signal."
        ),
        "page_role": "ITEM_DETAIL" if verified else "PUBLIC_API_LISTING",
        "listing_status": listing.listing_status,
        "verified": verified,
    }
    if exact_item_evidence:
        verification_row["item_page_status"] = exact_item_evidence.get("status")
        verification_row["page_sha256"] = exact_item_evidence.get("page_sha256")
        verification_row["response_bytes"] = exact_item_evidence.get("response_bytes")
        if exact_item_evidence.get("error"):
            verification_row["error"] = exact_item_evidence.get("error")

    candidate: dict[str, Any] = {
        "title": listing.title,
        "scenario": "WAREHOUSE_SURPLUS",
        "opportunity_state": "ACTIVE_OPPORTUNITY" if analysis_eligible else "STRONG_LEAD_REQUIRES_VERIFICATION",
        "reason": (
            "active Auksjonen clothing-inventory lot with verified exact item-page evidence"
            if verified
            else "active public API clothing-inventory lot; exact item-page verification remains required"
        ),
        "page_role": "ITEM_LISTING",
        "opportunity_identity": listing.url,
        "identity_stable": True,
        "listing_status": listing.listing_status,
        "top5_eligible": bool(top5_eligible),
        "analysis_eligible": analysis_eligible,
        "verified": verified,
        "source_urls": [listing.url],
        "source_providers": ["Auksjonen.no"],
        "textile_category": "CLOTHING_INVENTORY",
        "inventory_type": "clothing_inventory_lot",
        "location": _location(listing),
        "quantity": quantity,
        "condition": _observed(exact_item_evidence, "condition"),
        "source_description": _observed(exact_item_evidence, "description"),
        "price_nok": price_nok,
        "price_kind": price_kind,
        "current_bid_nok": listing.current_bid_nok,
        "buy_now_price_nok": listing.buy_now_price_nok,
        "start_price_nok": listing.start_price_nok,
        "source_object_id": str(listing.object_id),
        "auction_occurrence_id": f"auksjonen-auction:{listing.auction_id}:object:{listing.object_id}",
        "source_postal_code": _observed(exact_item_evidence, "source_postal_code") or listing.zip_code,
        "source_city": _observed(exact_item_evidence, "source_city") or listing.city,
        "weight_kg": _observed(exact_item_evidence, "weight_kg"),
        "length_cm": _observed(exact_item_evidence, "length_cm"),
        "width_cm": _observed(exact_item_evidence, "width_cm"),
        "height_cm": _observed(exact_item_evidence, "height_cm"),
        "pallet_count": _observed(exact_item_evidence, "pallet_count"),
        "buyer_premium_percent": _observed(exact_item_evidence, "buyer_premium_percent"),
        "vat_percent": _observed(exact_item_evidence, "vat_percent"),
        "exact_item_page_verified": verified,
        "shipping_details_source": _observed(exact_item_evidence, "shipping_details_source"),
        "source_item_url": listing.url,
        "source_image_urls": list(exact_item_evidence.get("image_urls") or []) if exact_item_evidence else [],
        "source_image_count": int(exact_item_evidence.get("image_count") or 0) if exact_item_evidence else 0,
        "visual_quantity_inference_performed": False,
        "evidence_signals": evidence_signals,
        "verification": [verification_row],
        "verification_blockers": blockers,
        "analysis_tasks": list(AUKSJONEN_ANALYSIS_TASKS),
        "missing_information": blockers,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    return candidate


def build_auksjonen_discovery_result(
    collection: AuksjonenLiveClothingCollection,
    *,
    exact_item_evidence: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    opportunities = collection.inventory_opportunities
    evidence = exact_item_evidence or {}
    candidates = [
        auksjonen_listing_to_discovery_candidate(
            listing,
            top5_eligible=index < 5,
            exact_item_evidence=evidence.get(listing.url),
        )
        for index, listing in enumerate(opportunities)
    ]
    return {
        "all_discovered_candidates": candidates,
        "discovery_top5": candidates[:5],
    }


def build_auksjonen_unified_report(
    collection: AuksjonenLiveClothingCollection,
    *,
    exact_item_evidence: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    result = build_auksjonen_discovery_result(collection, exact_item_evidence=exact_item_evidence)
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
    *,
    exact_item_evidence: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    result, report = build_auksjonen_unified_report(
        collection,
        exact_item_evidence=exact_item_evidence,
    )

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
