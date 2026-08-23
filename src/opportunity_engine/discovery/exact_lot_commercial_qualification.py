"""Conservative source-fact qualification for verified exact-lot pages.

Stage 3 may prove that a fetched item page is an ``EXACT_LOT_CANDIDATE``.
This module performs the next read-only step: extract item-specific commercial
facts from the original page and decide whether the lot is ready to enter the
existing financial-analysis workflow.

The module never estimates FX, delivery cost, resale value, or profit. Missing
commercial facts fail closed and all automatic commercial actions remain off.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult

SCHEMA_VERSION = "exact-lot-commercial-qualification-1.0"
EXACT_LOT_CANDIDATE = "EXACT_LOT_CANDIDATE"


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _safety() -> dict[str, bool]:
    return {
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _parse_number(value: str) -> float:
    raw = value.strip().replace("\u00a0", "").replace(" ", "")
    # Swedish marketplace prices commonly use dots as thousands separators.
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
        raw = raw.replace(".", "")
    elif "," in raw and "." not in raw:
        raw = raw.replace(",", ".")
    return float(raw)


def _normalise_blocket_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").casefold()
    path = parsed.path.casefold().rstrip("/")
    return host in {"blocket.se", "www.blocket.se"} and bool(
        re.search(r"/recommerce/forsale/item/\d+$", path)
    )


def _extract_price(text: str) -> dict[str, Any] | None:
    # Anchor to Blocket's primary listing-price label so related-card prices do
    # not replace the item's own price.
    match = re.search(
        r"\bSäljes\s+([0-9][0-9\s.,]{0,16})\s*(kr|SEK)\b",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    amount = _parse_number(match.group(1))
    return {
        "amount": amount,
        "currency": "SEK",
        "kind": "SOURCE_PRICE",
        "is_final_payable_price": False,
    }


def _clean_label(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" ,.;:-")


def _extract_quantity(text: str) -> dict[str, Any] | None:
    components: list[dict[str, Any]] = []
    match = re.search(
        r"\bMängd\s*:\s*(\d+)\s*st\.?\s+([A-Za-zÅÄÖåäö ]+?)\s*\+\s*"
        r"(\d+)\s*st\.?\s+([A-Za-zÅÄÖåäö]+)",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        components = [
            {"count": int(match.group(1)), "label": _clean_label(match.group(2)).casefold()},
            {"count": int(match.group(3)), "label": _clean_label(match.group(4)).casefold()},
        ]
    else:
        single = re.search(
            r"\bMängd\s*:\s*(\d+)\s*st\.?\b",
            text,
            flags=re.IGNORECASE,
        )
        if single:
            components = [{"count": int(single.group(1)), "label": "units"}]

    scope = None
    scope_match = re.search(
        r"\bkomplett(?:\s+paket)?\s+för(?:\s+en)?\s+(\d+)\s*x\s*(\d+)\s*"
        r"(?:m|meter)?\s*(?:pool)?",
        text,
        flags=re.IGNORECASE,
    )
    if scope_match:
        scope = f"{scope_match.group(1)}x{scope_match.group(2)}m pool"

    if not components:
        return None
    return {
        "total_units": sum(item["count"] for item in components),
        "components": components,
        "package_scope": scope,
    }


def _extract_condition(text: str) -> str | None:
    lowered = text.casefold()
    if "nytt skick - helt ny" in lowered or "helt nya" in lowered:
        return "NEW"
    return None


def _extract_location(text: str, *, country_code: str) -> dict[str, str] | None:
    match = re.search(
        r"\b([A-ZÅÄÖ][A-Za-zÅÄÖåäö-]+(?:vägen|gatan|väg|gata)\s+\d+[A-Za-z]?)\s+"
        r"(\d{5})\s+(.+?)(?=\s+(?:Ytterligare|Se butik|Verifierat|Frakt|Zurface|$))",
        text,
    )
    if not match:
        return None
    locality = _clean_label(match.group(3))
    if not locality:
        return None
    return {
        "street_address": _clean_label(match.group(1)),
        "postal_code": match.group(2),
        "locality": locality,
        "country_code": country_code,
    }


def _extract_seller(text: str, location: Mapping[str, str] | None) -> dict[str, Any] | None:
    if not location:
        return None
    street = re.escape(location["street_address"])
    match = re.search(
        rf"\b([A-ZÅÄÖ][A-Za-z0-9ÅÄÖåäö&.-]+(?:\s+[A-ZÅÄÖ][A-Za-z0-9ÅÄÖåäö&.-]+){{0,3}})\s+{street}\b",
        text,
    )
    if not match:
        return None
    name = _clean_label(match.group(1))
    return {
        "name": name,
        "verified_company": "Verifierat företag".casefold() in text.casefold(),
    }


def _extract_logistics(text: str) -> dict[str, Any]:
    lowered = text.casefold()
    shipping_available = "frakt och leverans" in lowered or "frakt" in lowered or "leverans" in lowered
    priced = re.search(
        r"(?:frakt|leverans)[^0-9]{0,40}([0-9][0-9\s.,]{0,12})\s*(kr|sek)\b",
        text,
        flags=re.IGNORECASE,
    )
    if priced:
        return {
            "shipping_available": True,
            "shipping_price_known": True,
            "shipping_cost": _parse_number(priced.group(1)),
            "shipping_currency": "SEK",
            "status": "AVAILABLE_PRICED",
        }
    if shipping_available:
        return {
            "shipping_available": True,
            "shipping_price_known": False,
            "shipping_cost": None,
            "shipping_currency": None,
            "status": "AVAILABLE_UNPRICED",
        }
    return {
        "shipping_available": False,
        "shipping_price_known": False,
        "shipping_cost": None,
        "shipping_currency": None,
        "status": "NOT_PROVEN",
    }


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "BLOCKED_NOT_EXACT_LOT",
        "block_reason": reason,
        "exact_lot_status": "NOT_CONFIRMED",
        "source_facts": None,
        "analysis_state": "REQUIRES_VERIFICATION",
        "required_analysis_tasks": ["verify one exact item page before commercial qualification"],
        "financial_readiness": {"ready_for_financial_engine": False},
        "financial_decision": None,
        "next_human_action": {"action": "VERIFY_EXACT_LOT"},
        **_safety(),
    }


def qualify_exact_lot_commercial_page(
    verified_page: Mapping[str, Any],
    page: PageFetchResult,
) -> dict[str, Any]:
    """Extract source facts from one already-verified exact-lot item page.

    Currently Blocket item pages are supported because Stage 3 produced one
    confirmed candidate there. Other sources fail closed until a source parser
    is proven with tests and direct-page evidence.
    """
    if verified_page.get("classification") != EXACT_LOT_CANDIDATE:
        return _blocked("INPUT_CLASSIFICATION_NOT_EXACT_LOT_CANDIDATE")
    if verified_page.get("fetch_ok") is not True:
        return _blocked("STAGE3_PAGE_FETCH_NOT_CONFIRMED")
    evidence = verified_page.get("evidence") or {}
    if not isinstance(evidence, Mapping) or evidence.get("item_specific_url_evidence") is not True:
        return _blocked("ITEM_SPECIFIC_URL_NOT_PROVEN")
    if not page.ok:
        return _blocked("COMMERCIAL_PAGE_FETCH_FAILED")

    source_url = _compact(page.final_url or verified_page.get("final_url") or verified_page.get("url"))
    if not _normalise_blocket_url(source_url):
        return _blocked("UNSUPPORTED_OR_NON_ITEM_SOURCE_URL")

    text = _compact(page.text)
    market_code = _compact(verified_page.get("market_code")).upper() or "SE"
    price = _extract_price(text)
    quantity = _extract_quantity(text)
    condition = _extract_condition(text)
    location = _extract_location(text, country_code=market_code)
    seller = _extract_seller(text, location)
    logistics = _extract_logistics(text)

    source_facts = {
        "url": source_url,
        "title": _compact(page.title),
        "market_code": market_code,
        "price": price,
        "quantity": quantity,
        "condition": condition,
        "location": location,
        "seller": seller,
        "logistics": logistics,
    }

    missing_source_facts = [
        label
        for label, value in (
            ("main listing price", price),
            ("quantity", quantity),
            ("condition", condition),
            ("location", location),
        )
        if value is None
    ]
    if missing_source_facts:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "REQUIRES_VERIFICATION",
            "block_reason": "SOURCE_FACT_EXTRACTION_INCOMPLETE",
            "exact_lot_status": "REQUIRES_VERIFICATION",
            "source_facts": source_facts,
            "analysis_state": "REQUIRES_VERIFICATION",
            "required_analysis_tasks": [
                f"verify source fact: {item}" for item in missing_source_facts
            ],
            "financial_readiness": {"ready_for_financial_engine": False},
            "financial_decision": None,
            "next_human_action": {"action": "VERIFY_SOURCE_FACTS"},
            **_safety(),
        }

    tasks = ["document final payable price in NOK including any fees, tax and FX basis"]
    if logistics["shipping_price_known"] is not True:
        tasks.append("obtain pickup or delivery cost in NOK")
    tasks.append("document conservative resale value and comparables")

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "QUALIFIED_SOURCE_FACTS",
        "block_reason": None,
        "exact_lot_status": "CONFIRMED",
        "source_facts": source_facts,
        "analysis_state": "REQUIRES_COMMERCIAL_INPUTS",
        "required_analysis_tasks": tasks,
        "financial_readiness": {
            "ready_for_financial_engine": False,
            "source_price_amount": price["amount"],
            "source_price_currency": price["currency"],
            "transport_nok": None,
            "conservative_resale_nok": None,
        },
        "financial_decision": None,
        "next_human_action": {
            "action": "COMPLETE_LOGISTICS_AND_MARKET_VALUE",
            "source_url": source_url,
        },
        **_safety(),
    }
