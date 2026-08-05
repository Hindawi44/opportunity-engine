"""Official-domain watch for Fashion Stock Netherlands clothing stock offers.

The source is treated as decision-support intelligence. Large lots are never
rejected because of size; missing public details stay visible as early B2B signals
for the human operator to inspect, calculate, negotiate, and decide.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import os
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from opportunity_engine.discovery.brave_market_signal_radar import (
    _canonical_url,
    _compact,
    _default_provider_factory,
    _iso_utc,
)
from opportunity_engine.discovery.merkandi_b2b_liquidation_feed import (
    _AUTHENTICITY_TERMS,
    _CLOTHING_TERMS,
    _COMMERCIAL_TERMS,
    _CONDITION_TERMS,
    _MANIFEST_TERMS,
    _PRIVATE_SINGLE_TERMS,
    _SHIPPING_TERMS,
    _extract_brands,
    _extract_inventory_quantity,
    _extract_location,
    _extract_moq,
    _extract_price,
    _lot_size_band,
    _matched_terms,
    _official_domain,
    _safety_payload,
)
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider

SCHEMA_VERSION = "fashion-stock-netherlands-feed-1.0"
FEED_FAMILY = "FASHION_STOCK_NETHERLANDS_FEED_V1"
SOURCE_NAME = "Fashion Stock Netherlands"
APPROVED_DOMAINS = ("fashion-stock.eu", "fashionstock.eu", "fashion-stock.nl")
SEARCH_REGION = "NL"
SEARCH_LANGUAGE = "en"
DEFAULT_RESULTS_PER_QUERY = 8
MAX_RESULTS_PER_QUERY = 10
MAX_ACCEPTED = 10
DEFAULT_FRESHNESS = "pm"
QUERIES = (
    'site:fashion-stock.eu (stock clothes OR "clothing stock" OR "brand clothing") '
    '(wholesale OR bulk OR stocklot OR leftovers OR overproduction OR clearance)',
    'site:fashionstock.eu (stock clothing OR "wholesale fashion" OR "clothing lot") '
    '(pieces OR pcs OR quantity OR price OR order)',
)

ProviderFactory = Callable[[str, str, str | None], SearchProvider]


def _candidate_from_hit(
    hit: SearchHit,
    *,
    observed_at: datetime,
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(hit, SearchHit):
        return None, "INVALID_SEARCH_HIT"
    title = _compact(hit.title)
    description = _compact(hit.description)
    raw_url = _compact(hit.url)
    if not title or not raw_url:
        return None, "MISSING_TITLE_OR_URL"
    try:
        canonical_url = _canonical_url(raw_url)
    except ValueError:
        return None, "INVALID_URL"
    if not _official_domain(canonical_url, APPROVED_DOMAINS):
        return None, "UNAPPROVED_DOMAIN"
    path = urlsplit(canonical_url).path
    if path in {"", "/"}:
        return None, "GENERIC_HOME_PAGE"

    combined = f"{title} {description}".strip()
    clothing_terms = _matched_terms(combined, _CLOTHING_TERMS)
    commercial_terms = _matched_terms(combined, _COMMERCIAL_TERMS)
    if not clothing_terms:
        return None, "NOT_CLOTHING_INVENTORY"
    if not commercial_terms:
        return None, "NO_B2B_STOCK_SIGNAL"
    if _matched_terms(combined, _PRIVATE_SINGLE_TERMS):
        return None, "PRIVATE_OR_SINGLE_ITEM_LISTING"

    moq, moq_unit, moq_span = _extract_moq(combined)
    quantity, quantity_unit = _extract_inventory_quantity(combined, moq_span=moq_span)
    if quantity is not None and quantity <= 1:
        return None, "SINGLE_ITEM_LISTING"
    price_text, price, currency, price_basis = _extract_price(combined)
    manifest_terms = _matched_terms(combined, _MANIFEST_TERMS)
    brands = _extract_brands(combined)
    authenticity_terms = _matched_terms(combined, _AUTHENTICITY_TERMS)
    condition_terms = _matched_terms(combined, _CONDITION_TERMS)
    shipping_terms = _matched_terms(combined, _SHIPPING_TERMS)
    stock_location = _extract_location(combined) or "Netherlands"

    missing_information: list[str] = []
    if quantity is None:
        missing_information.append("QUANTITY")
    if moq is None:
        missing_information.append("MINIMUM_ORDER")
    if price is None or currency is None:
        missing_information.append("VISIBLE_PRICE")
    if not manifest_terms:
        missing_information.append("MANIFEST_OR_STOCK_LIST")
    if brands and not authenticity_terms:
        missing_information.append("BRAND_AUTHENTICITY_EVIDENCE")
    if not shipping_terms:
        missing_information.append("SHIPPING_TERMS")

    specific_offer = any(value is not None for value in (quantity, moq, price)) or "/stock/" in path or "shop_" in path
    opportunity_state = (
        "B2B_LEAD_REQUIRES_VERIFICATION"
        if specific_offer and len(missing_information) <= 2
        else "EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION"
    )
    page_role = "SPECIFIC_STOCK_OFFER" if specific_offer else "STOCK_CATALOGUE_SIGNAL"

    score = 42
    score += 10 if quantity is not None else 0
    score += 8 if moq is not None else 0
    score += 10 if price is not None and currency else 0
    score += 8 if brands else 0
    score += 7 if manifest_terms else 0
    score += 6 if authenticity_terms else 0
    score += 4 if condition_terms else 0
    score += 3 if shipping_terms else 0
    score += 2 if specific_offer else 0
    score = min(100, score)

    candidate_id = "fashion-stock-nl:" + sha256(canonical_url.encode("utf-8")).hexdigest()[:24]
    return {
        "candidate_id": candidate_id,
        "feed_family": FEED_FAMILY,
        "source_name": SOURCE_NAME,
        "official_domain": (urlsplit(canonical_url).hostname or "").casefold(),
        "source_url": canonical_url,
        "title": title[:1000],
        "description": (description or title)[:1500],
        "observed_at": _iso_utc(observed_at),
        "search_provider": _compact(hit.provider) or None,
        "page_role": page_role,
        "clothing_terms": clothing_terms,
        "commercial_terms": commercial_terms,
        "quantity": quantity,
        "quantity_unit": quantity_unit,
        "lot_size_band": _lot_size_band(quantity, quantity_unit),
        "minimum_order": moq,
        "minimum_order_unit": moq_unit,
        "price_text": price_text,
        "unit_price": price if price_basis == "PER_UNIT" else None,
        "total_price": price if price_basis != "PER_UNIT" else None,
        "price_basis": price_basis,
        "currency": currency,
        "condition_terms": condition_terms,
        "brands": brands,
        "stock_location": stock_location,
        "manifest_available": bool(manifest_terms),
        "manifest_terms": manifest_terms,
        "authenticity_evidence_visible": bool(authenticity_terms),
        "authenticity_terms": authenticity_terms,
        "shipping_information_present": bool(shipping_terms),
        "shipping_terms": shipping_terms,
        "seller_name": SOURCE_NAME,
        "seller_identity_status": "OFFICIAL_SOURCE_BRAND_REQUIRES_LEGAL_VERIFICATION",
        "missing_information": missing_information,
        "opportunity_state": opportunity_state,
        "verification_status": "UNVERIFIED_OFFICIAL_DOMAIN_SEARCH_RESULT",
        "b2b_relevance_score": score,
        "decision_owner": "HUMAN_OPERATOR",
        "quantity_size_rejection_applied": False,
        "qualification_blockers": [
            "VERIFY_OFFER_ACTIVE_AND_SPECIFIC",
            "VERIFY_COMPANY_LEGAL_IDENTITY",
            "VERIFY_COMPLETE_STOCK_LIST",
            "VERIFY_BRAND_AUTHENTICITY_AND_RESALE_RIGHTS",
            "VERIFY_SHIPPING_TO_NORWAY",
            "CALCULATE_FREIGHT_IMPORT_VAT_AND_LANDED_COST",
            *[f"MISSING_{item}" for item in missing_information],
        ],
        "recommended_operator_action": "OPEN_SOURCE_PAGE_COLLECT_NUMBERS_CALCULATE_NEGOTIATE_AND_DECIDE",
        **_safety_payload(),
    }, None


def fashion_stock_candidate_from_hit(
    hit: SearchHit, *, observed_at: datetime,
) -> dict[str, Any] | None:
    candidate, _ = _candidate_from_hit(hit, observed_at=observed_at)
    return candidate


def collect_fashion_stock_netherlands_feed(
    *,
    observed_at: datetime | None = None,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory = _default_provider_factory,
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
    freshness: str | None = DEFAULT_FRESHNESS,
) -> dict[str, Any]:
    if not 1 <= results_per_query <= MAX_RESULTS_PER_QUERY:
        raise ValueError(f"results_per_query must be between 1 and {MAX_RESULTS_PER_QUERY}")
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    env = environment if environment is not None else os.environ
    api_key = _compact(env.get("BRAVE_SEARCH_API_KEY")) or _compact(env.get("BRAVE_API_KEY"))

    source_report: dict[str, Any] = {
        "source_name": SOURCE_NAME,
        "approved_official_domains": list(APPROVED_DOMAINS),
        "queries": list(QUERIES),
        "search_region": SEARCH_REGION,
        "search_language": SEARCH_LANGUAGE,
        "query_budget": len(QUERIES),
        "queries_attempted": 0,
        "queries_succeeded": 0,
        "accepted_candidate_count": 0,
        "rejected_result_count": 0,
        "duplicate_result_count": 0,
        "rejection_reason_counts": {},
        "candidates": [],
        "errors": [],
        **_safety_payload(),
    }
    requests_made = 0
    if not api_key:
        source_report.update(status="BLOCKED_CONFIGURATION", block_reason="BRAVE_SEARCH_API_KEY_MISSING")
    else:
        try:
            provider = provider_factory(SEARCH_REGION, api_key, freshness)
        except Exception as exc:
            source_report.update(
                status="BLOCKED_RETRIEVAL",
                block_reason="PROVIDER_INITIALIZATION_FAILED",
                errors=[f"{type(exc).__name__}: {_compact(exc)[:300]}"],
            )
        else:
            accepted: dict[str, dict[str, Any]] = {}
            seen_urls: set[str] = set()
            rejection_counts: dict[str, int] = {}
            duplicates = 0
            for query in QUERIES:
                source_report["queries_attempted"] += 1
                requests_made += 1
                try:
                    hits = provider.search(query, count=results_per_query)
                    source_report["queries_succeeded"] += 1
                except Exception as exc:
                    source_report["errors"].append(f"{type(exc).__name__}: {_compact(exc)[:300]}")
                    continue
                for hit in hits:
                    try:
                        canonical_url = _canonical_url(_compact(getattr(hit, "url", "")))
                    except ValueError:
                        canonical_url = ""
                    if canonical_url and canonical_url in seen_urls:
                        duplicates += 1
                        continue
                    if canonical_url:
                        seen_urls.add(canonical_url)
                    candidate, rejection = _candidate_from_hit(hit, observed_at=now)
                    if candidate is None:
                        reason = rejection or "REJECTED_BY_GATE"
                        rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
                        continue
                    accepted[candidate["candidate_id"]] = candidate

            selected = sorted(
                accepted.values(),
                key=lambda item: (-int(item["b2b_relevance_score"]), str(item["source_url"])),
            )[:MAX_ACCEPTED]
            source_report.update(
                accepted_candidate_count=len(selected),
                rejected_result_count=sum(rejection_counts.values()),
                duplicate_result_count=duplicates,
                rejection_reason_counts=dict(sorted(rejection_counts.items())),
                candidates=selected,
                status=(
                    "SUCCESS" if selected
                    else "VALID_ZERO" if source_report["queries_succeeded"]
                    else "BLOCKED_RETRIEVAL"
                ),
                block_reason=None if source_report["queries_succeeded"] else "ALL_SEARCH_REQUESTS_FAILED",
            )

    status = _compact(source_report.get("status")).upper() or "UNKNOWN"
    candidates = source_report.get("candidates") or []
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso_utc(now),
        "feed_family": FEED_FAMILY,
        "purpose": "OFFICIAL_SOURCE_B2B_CLOTHING_STOCK_DECISION_SUPPORT",
        "approved_official_domains": list(APPROVED_DOMAINS),
        "source_count": 1,
        "query_budget_total": len(QUERIES),
        "requests_made": requests_made,
        "results_per_query": results_per_query,
        "freshness": freshness,
        "status_counts": {status: 1},
        "candidate_count": len(candidates),
        "candidates": candidates,
        "sources": [source_report],
        "operator_rule": "SURFACE_ALL_SERIOUS_STOCK_SIGNALS_CALCULATE_AND_LEAVE_DECISION_TO_HUMAN",
        "incomplete_signals_preserved": True,
        "quantity_size_rejection_enabled": False,
        "human_decision_required": True,
        "not_part_of_opportunity_top5": True,
        **_safety_payload(),
    }
