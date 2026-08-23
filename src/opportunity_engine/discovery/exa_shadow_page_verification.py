"""Bounded direct-page verification for Exa-only shadow discoveries.

Search results are observations, not opportunities. This stage fetches only URLs
returned by Exa that were not returned by Brave for the same market/query and
classifies the original page conservatively. It cannot activate Exa in
production or perform any commercial action.
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from typing import Any

from opportunity_engine.discovery.keyword_shadow_verification import (
    PageFetchResult,
    fetch_public_page,
)

SCHEMA_VERSION = "exa-shadow-page-verification-1.0"
LAB_FAMILY = "EXA_SHADOW_PAGE_VERIFICATION_V1"
SUPPORTED_MARKETS = frozenset({"NO", "SE", "DE", "FR", "IT", "NL"})
MAX_ALLOWED_PAGE_FETCHES = 30

EXACT_LOT_CANDIDATE = "EXACT_LOT_CANDIDATE"
ACTIVE_STOCK_SIGNAL = "ACTIVE_STOCK_SIGNAL"
SOURCE_INTELLIGENCE_ONLY = "SOURCE_INTELLIGENCE_ONLY"
INFO_OR_LEGAL_ONLY = "INFO_OR_LEGAL_ONLY"
UNPROVEN_PAGE = "UNPROVEN_PAGE"
FETCH_FAILED = "FETCH_FAILED"
NOT_FETCHED_BUDGET = "NOT_FETCHED_BUDGET"

PageFetcher = Callable[[str], PageFetchResult]

_INVENTORY_MARKERS = (
    "restlager",
    "varelager",
    "vareparti",
    "lagerparti",
    "parti med",
    "overskottslager",
    "överskottslager",
    "restparti",
    "restpartier",
    "varulager",
    "restposten",
    "sonderposten",
    "sonderpost",
    "warenlager",
    "lagerbestand",
    "stock",
    "déstockage",
    "destockage",
    "invendus",
    "lot de marchandises",
    "lots de marchandises",
    "magazzino",
    "scorte",
    "stock di merce",
    "lotti",
    "lotto",
    "voorraad",
    "restpartij",
    "restpartijen",
    "partijhandel",
    "partijgoederen",
    "surplus",
    "overstock",
    "deadstock",
)

_DIRECT_SALE_MARKERS = (
    "selges",
    "til salgs",
    "for salg",
    "säljes",
    "till salu",
    "zu verkaufen",
    "zum verkauf",
    "verkauf ab lager",
    "vente de stock",
    "à vendre",
    "a vendre",
    "en vente",
    "vendita stock",
    "in vendita",
    "te koop",
    "voor verkoop",
    "beschikbaar voor zakelijke kopers",
    "available for sale",
    "available for buyers",
    "auction",
    "auksjon",
    "auktion",
    "enchères",
    "encheres",
    "asta",
    "veiling",
)

_BUYER_OR_SOURCE_MARKERS = (
    "vi kjøper",
    "kjøper restlager",
    "kjøper varepartier",
    "selg ditt varelager",
    "sälj ditt lager",
    "vi köper",
    "köper restlager",
    "wir kaufen",
    "ankauf von",
    "ankauf ihrer",
    "aufkäufer",
    "aufkaeufer",
    "nous achetons",
    "vendre votre stock",
    "acquistiamo",
    "acquisto stock",
    "vendere il tuo stock",
    "wij kopen",
    "inkoop voorraad",
    "verkoop uw voorraad",
    "sell your stock",
    "sell your inventory",
)

_INFO_OR_LEGAL_MARKERS = (
    "règles à respecter",
    "regles a respecter",
    "code de commerce",
    "service public",
    "obligations légales",
    "obligations legales",
    "loi ",
    "wetgeving",
    "regelgeving",
    "normativa",
    "guida completa",
    "guide complet",
    "how to ",
    "slik gjør du",
    "slik gjor du",
    "regler for",
    "rules for",
)

_PRICE_RE = re.compile(
    r"(?:\b\d[\d\s.,]{0,14}\s*(?:nok|sek|eur|euro|kr\.?|€)\b|(?:€|kr\.?)[\s]*\d)",
    re.IGNORECASE,
)
_QUANTITY_RE = re.compile(
    r"\b\d[\d\s.,]{0,10}\s*(?:stk|st\.?|pcs|pieces|pièces|pieces|pezzi|stuks|"
    r"units|paller|pallets|paletten|pallet|kg|tonn|ton|tonnes|meter|metri|mètres|"
    r"metres|ruller|rollen|rolls|kartonger|kartons|cartons)\b",
    re.IGNORECASE,
)


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _classify_page(*, title: str, text: str) -> tuple[str, dict[str, bool]]:
    combined = f"{_compact(title)} {_compact(text)}".casefold()
    has_inventory = _contains_any(combined, _INVENTORY_MARKERS)
    has_direct_sale = _contains_any(combined, _DIRECT_SALE_MARKERS)
    has_buyer_source = _contains_any(combined, _BUYER_OR_SOURCE_MARKERS)
    has_info_legal = _contains_any(combined, _INFO_OR_LEGAL_MARKERS)
    has_price = bool(_PRICE_RE.search(combined))
    has_quantity = bool(_QUANTITY_RE.search(combined))

    evidence = {
        "inventory_evidence": has_inventory,
        "direct_sale_evidence": has_direct_sale,
        "buyer_or_source_evidence": has_buyer_source,
        "info_or_legal_evidence": has_info_legal,
        "price_evidence": has_price,
        "quantity_evidence": has_quantity,
    }

    if has_inventory and has_direct_sale and has_quantity and has_price and not has_info_legal:
        return EXACT_LOT_CANDIDATE, evidence
    if has_inventory and has_direct_sale and not has_info_legal and not has_buyer_source:
        return ACTIVE_STOCK_SIGNAL, evidence
    if has_inventory and has_buyer_source and not has_direct_sale:
        return SOURCE_INTELLIGENCE_ONLY, evidence
    if has_info_legal and not (has_inventory and has_direct_sale and has_quantity and has_price):
        return INFO_OR_LEGAL_ONLY, evidence
    if has_inventory and has_buyer_source:
        return SOURCE_INTELLIGENCE_ONLY, evidence
    return UNPROVEN_PAGE, evidence


def _base_payload(*, max_page_fetches: int) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "lab_family": LAB_FAMILY,
        "shadow_only": True,
        "max_page_fetches": max_page_fetches,
        "production_provider_activation": False,
        "promotion_to_live_engine_enabled": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
        "interpretation_guard": (
            "Verified pages remain shadow evidence. EXACT_LOT_CANDIDATE is not a commercial decision."
        ),
    }


def verify_exa_unique_pages(
    benchmark_report: dict[str, Any],
    *,
    page_fetcher: PageFetcher = fetch_public_page,
    max_page_fetches: int = 18,
) -> dict[str, Any]:
    """Verify Exa-only URLs from one successful Exa-vs-Brave shadow report."""
    if not 1 <= max_page_fetches <= MAX_ALLOWED_PAGE_FETCHES:
        raise ValueError(f"max_page_fetches must be between 1 and {MAX_ALLOWED_PAGE_FETCHES}")

    base = _base_payload(max_page_fetches=max_page_fetches)
    if benchmark_report.get("status") != "SUCCESS":
        return {
            **base,
            "status": "BLOCKED_INPUT",
            "block_reason": "BENCHMARK_NOT_SUCCESSFUL",
            "exa_unique_url_count": 0,
            "verified_pages": [],
        }
    if benchmark_report.get("shadow_only") is not True:
        return {
            **base,
            "status": "BLOCKED_INPUT",
            "block_reason": "INPUT_NOT_SHADOW_ONLY",
            "exa_unique_url_count": 0,
            "verified_pages": [],
        }

    candidates: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for market_row in benchmark_report.get("market_results") or []:
        if not isinstance(market_row, dict):
            continue
        market = _compact(market_row.get("market_code")).upper()
        if market not in SUPPORTED_MARKETS:
            continue
        brave_results = (market_row.get("brave") or {}).get("results") or []
        brave_urls = {
            _compact(item.get("url"))
            for item in brave_results
            if isinstance(item, dict) and _compact(item.get("url"))
        }
        for item in (market_row.get("exa") or {}).get("results") or []:
            if not isinstance(item, dict):
                continue
            url = _compact(item.get("url"))
            if not url or url in brave_urls or url in seen_urls:
                continue
            seen_urls.add(url)
            candidates.append(
                {
                    "market_code": market,
                    "query": _compact(market_row.get("query")),
                    "title": _compact(item.get("title")),
                    "url": url,
                    "domain": _compact(item.get("domain")),
                }
            )

    verified_pages: list[dict[str, Any]] = []
    attempted = 0
    succeeded = 0
    budget_exhausted = 0

    for candidate in candidates:
        if attempted >= max_page_fetches:
            budget_exhausted += 1
            verified_pages.append(
                {
                    **candidate,
                    "classification": NOT_FETCHED_BUDGET,
                    "fetch_ok": False,
                    "status_code": None,
                    "final_url": candidate["url"],
                    "fetch_error": "PAGE_BUDGET_EXHAUSTED",
                    "evidence": {},
                }
            )
            continue

        attempted += 1
        fetched = page_fetcher(candidate["url"])
        if not fetched.ok:
            verified_pages.append(
                {
                    **candidate,
                    "classification": FETCH_FAILED,
                    "fetch_ok": False,
                    "status_code": fetched.status_code,
                    "final_url": fetched.final_url,
                    "fetch_error": fetched.error,
                    "evidence": {},
                }
            )
            continue

        succeeded += 1
        classification, evidence = _classify_page(
            title=fetched.title or candidate["title"],
            text=fetched.text,
        )
        verified_pages.append(
            {
                **candidate,
                "classification": classification,
                "fetch_ok": True,
                "status_code": fetched.status_code,
                "final_url": fetched.final_url,
                "fetch_error": None,
                "truncated": fetched.truncated,
                "evidence": evidence,
            }
        )

    counts = Counter(item["classification"] for item in verified_pages)
    market_summary: list[dict[str, Any]] = []
    for market in sorted(SUPPORTED_MARKETS):
        market_items = [item for item in verified_pages if item["market_code"] == market]
        if not market_items:
            continue
        market_counts = Counter(item["classification"] for item in market_items)
        market_summary.append(
            {
                "market_code": market,
                "exa_unique_url_count": len(market_items),
                "exact_lot_candidate_count": market_counts[EXACT_LOT_CANDIDATE],
                "active_stock_signal_count": market_counts[ACTIVE_STOCK_SIGNAL],
                "source_intelligence_only_count": market_counts[SOURCE_INTELLIGENCE_ONLY],
                "info_or_legal_only_count": market_counts[INFO_OR_LEGAL_ONLY],
                "unproven_page_count": market_counts[UNPROVEN_PAGE],
                "fetch_failed_count": market_counts[FETCH_FAILED],
                "budget_not_fetched_count": market_counts[NOT_FETCHED_BUDGET],
            }
        )

    return {
        **base,
        "status": "SUCCESS",
        "block_reason": None,
        "exa_unique_url_count": len(candidates),
        "page_fetches_attempted": attempted,
        "page_fetches_succeeded": succeeded,
        "budget_exhausted_count": budget_exhausted,
        "exact_lot_candidate_count": counts[EXACT_LOT_CANDIDATE],
        "active_stock_signal_count": counts[ACTIVE_STOCK_SIGNAL],
        "source_intelligence_only_count": counts[SOURCE_INTELLIGENCE_ONLY],
        "info_or_legal_only_count": counts[INFO_OR_LEGAL_ONLY],
        "unproven_page_count": counts[UNPROVEN_PAGE],
        "fetch_failed_count": counts[FETCH_FAILED],
        "market_summary": market_summary,
        "verified_pages": verified_pages,
    }
