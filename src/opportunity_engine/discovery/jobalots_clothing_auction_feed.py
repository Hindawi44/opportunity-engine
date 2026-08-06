"""Bounded official-domain watch for Jobalots clothing liquidation lots.

The feed surfaces clothing, footwear, and textile job lots from Jobalots for
human review. Active, incomplete, unmanifested, and ended lots remain decision-
support signals; the engine never bids, reserves, purchases, or pays.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import os
import re
from typing import Any, Callable, Mapping
from urllib.parse import unquote, urlsplit

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
    _parse_number,
    _safety_payload,
)
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider

SCHEMA_VERSION = "jobalots-clothing-auction-feed-1.0"
FEED_FAMILY = "JOBALOTS_CLOTHING_LIQUIDATION_AUCTION_FEED_V1"
SOURCE_NAME = "Jobalots"
SOURCE_REGION = "UK_AND_EU"
APPROVED_DOMAINS = ("jobalots.com",)
SEARCH_REGION = "GB"
SEARCH_LANGUAGE = "en"
DEFAULT_RESULTS_PER_QUERY = 8
MAX_RESULTS_PER_QUERY = 10
MAX_ACCEPTED = 12
DEFAULT_FRESHNESS = "pm"
QUERIES = (
    'site:jobalots.com/en/products/ (clothing OR apparel OR garments OR footwear OR shoes) '
    '(pallet OR box OR "job lot" OR wholesale OR liquidation OR returns OR overstock)',
    'site:jobalots.com ("clothing pallet" OR "clothing job lot" OR "apparel wholesale") '
    '(auction OR bid OR manifest OR RRP OR "customer returns" OR clearance)',
)

ProviderFactory = Callable[[str, str, str | None], SearchProvider]

_SOURCE_CLOTHING_TERMS = (
    "footwear",
    "shoes",
    "trainers",
    "swimwear",
    "hoodies",
    "t-shirts",
    "womens clothing",
    "women's clothing",
    "mens clothing",
    "men's clothing",
    "kids clothing",
)
_SOURCE_COMMERCIAL_TERMS = (
    "pallet",
    "pallets",
    "box",
    "boxes",
    "job lot",
    "job lots",
    "auction",
    "auctions",
    "bid",
    "bidding",
    "customer returns",
    "overstock",
    "clearance",
    "rrp",
)
_AUCTION_TERMS = (
    "auction",
    "auctions",
    "current bid",
    "starting bid",
    "place bid",
    "joining auction",
    "bid now",
    "bidding",
)
_ENDED_TERMS = (
    "auction ended",
    "auction has ended",
    "this auction has ended",
    "sold out",
    "lot closed",
    "bidding closed",
)
_UNMANIFESTED_TERMS = (
    "unmanifested",
    "no manifest",
    "without manifest",
)
_MANIFEST_TERMS = (
    "manifest",
    "manifest details",
    "download manifest",
    "full manifest",
    "itemised contents",
    "itemized contents",
    "stock list",
)
_CONDITION_SOURCE_TERMS = (
    "brand new",
    "customer returns",
    "unchecked returns",
    "returns unchecked",
    "overstock",
    "clearance",
    "surplus",
)
_KNOWN_BRANDS = (
    "calvin klein",
    "new balance",
    "g-star",
    "nike",
    "adidas",
    "puma",
    "reebok",
    "regatta",
    "under armour",
    "tommy hilfiger",
)

_PALLET_RE = re.compile(
    r"(?P<amount>\d{1,6}(?:[\s.,]\d{3})*)\s*(?P<unit>pallets?|boxes?|lots?)\b",
    re.IGNORECASE,
)
_BID_RE = re.compile(
    r"\b(?:current\s+bid|starting\s+bid|bid\s+from|opening\s+bid)\s*[:\-]?\s*"
    r"(?P<symbol>£|€|\$)?\s*(?P<amount>\d{1,9}(?:[\s.,]\d{3})*(?:[.,]\d{1,2})?)\s*"
    r"(?P<code>GBP|EUR|USD)?",
    re.IGNORECASE,
)
_RRP_RE = re.compile(
    r"\b(?:rrp|retail\s+value|estimated\s+retail\s+value)\s*[:\-]?\s*"
    r"(?P<symbol>£|€|\$)?\s*(?P<amount>\d{1,9}(?:[\s.,]\d{3})*(?:[.,]\d{1,2})?)\s*"
    r"(?P<code>GBP|EUR|USD)?",
    re.IGNORECASE,
)
_LOT_REF_RE = re.compile(
    r"\b(?:lot|auction)\s*(?:number|no\.?|#|ref(?:erence)?)?\s*[:#\-]?\s*"
    r"(?P<reference>[A-Z0-9][A-Z0-9._-]{2,40})\b",
    re.IGNORECASE,
)
_END_TEXT_RE = re.compile(
    r"\b(?:auction\s+ends?|ends?|closing)\s*[:\-]\s*"
    r"(?P<value>[^|;\n]{4,80})",
    re.IGNORECASE,
)


def _currency(symbol: str | None, code: str | None) -> str | None:
    explicit = (code or "").upper()
    if explicit:
        return explicit
    return {"£": "GBP", "€": "EUR", "$": "USD"}.get(symbol or "")


def _extract_named_money(
    pattern: re.Pattern[str], text: str
) -> tuple[str | None, float | None]:
    match = pattern.search(text)
    if not match:
        return None, None
    amount = _parse_number(match.group("amount"))
    return _currency(match.group("symbol"), match.group("code")), amount


def _extract_lot_units(text: str) -> tuple[float | None, str | None]:
    match = _PALLET_RE.search(text)
    if not match:
        return None, None
    amount = _parse_number(match.group("amount"))
    unit = match.group("unit").casefold()
    if unit.startswith("pallet"):
        return amount, "pallets"
    if unit.startswith("box"):
        return amount, "boxes"
    return amount, "lots"


def _lot_size(quantity: float | None, quantity_unit: str | None, lot_units: float | None) -> str:
    if quantity is not None:
        return _lot_size_band(quantity, quantity_unit)
    if lot_units is None:
        return "UNKNOWN"
    if lot_units <= 1:
        return "SMALL"
    if lot_units <= 5:
        return "MEDIUM"
    if lot_units <= 20:
        return "LARGE"
    return "VERY_LARGE"


def _source_brands(text: str) -> list[str]:
    brands = _extract_brands(text)
    brands.extend(term.title() for term in _matched_terms(text, _KNOWN_BRANDS))
    return sorted({brand for brand in brands if brand})[:15]


def _lot_reference(text: str, canonical_url: str) -> str | None:
    match = _LOT_REF_RE.search(text)
    if match:
        return match.group("reference")[:60]
    path = urlsplit(canonical_url).path.rstrip("/")
    if "/products/" in path:
        slug = unquote(path.rsplit("/", 1)[-1]).strip()
        return slug[:80] or None
    return None


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

    path = urlsplit(canonical_url).path.casefold()
    if path in {"", "/", "/en", "/en/"}:
        return None, "GENERIC_HOME_PAGE"

    combined = f"{title} {description}".strip()
    clothing_terms = sorted(
        set(_matched_terms(combined, _CLOTHING_TERMS))
        | set(_matched_terms(combined, _SOURCE_CLOTHING_TERMS))
    )
    commercial_terms = sorted(
        set(_matched_terms(combined, _COMMERCIAL_TERMS))
        | set(_matched_terms(combined, _SOURCE_COMMERCIAL_TERMS))
    )
    if not clothing_terms:
        return None, "NOT_CLOTHING_OR_TEXTILE_STOCK"
    if not commercial_terms:
        return None, "NO_JOB_LOT_OR_AUCTION_SIGNAL"
    if _matched_terms(combined, _PRIVATE_SINGLE_TERMS):
        return None, "PRIVATE_OR_SINGLE_ITEM_LISTING"

    minimum_order, minimum_order_unit, minimum_span = _extract_moq(combined)
    quantity, quantity_unit = _extract_inventory_quantity(
        combined,
        moq_span=minimum_span,
    )
    lot_units, lot_unit_type = _extract_lot_units(combined)
    if quantity is not None and quantity <= 1 and lot_units is None:
        return None, "SINGLE_RETAIL_ITEM"

    bid_currency, current_bid = _extract_named_money(_BID_RE, combined)
    rrp_currency, estimated_retail_value = _extract_named_money(_RRP_RE, combined)
    price_text, fallback_price, fallback_currency, price_basis = _extract_price(combined)
    if current_bid is not None:
        total_price = current_bid
        currency = bid_currency
        price_basis = "CURRENT_OR_STARTING_BID"
    else:
        total_price = fallback_price
        currency = fallback_currency

    unmanifested_terms = _matched_terms(combined, _UNMANIFESTED_TERMS)
    manifest_terms = _matched_terms(combined, _MANIFEST_TERMS)
    manifest_available = bool(manifest_terms) and not bool(unmanifested_terms)
    brands = _source_brands(combined)
    authenticity_terms = _matched_terms(combined, _AUTHENTICITY_TERMS)
    condition_terms = sorted(
        set(_matched_terms(combined, _CONDITION_TERMS))
        | set(_matched_terms(combined, _CONDITION_SOURCE_TERMS))
    )
    shipping_terms = _matched_terms(combined, _SHIPPING_TERMS)
    auction_terms = _matched_terms(combined, _AUCTION_TERMS)
    ended_terms = _matched_terms(combined, _ENDED_TERMS)

    page_role = (
        "SPECIFIC_AUCTION_OR_JOB_LOT"
        if "/products/" in path
        else "CLOTHING_AUCTION_CATALOGUE_SIGNAL"
    )
    listing_status = "ENDED" if ended_terms else "ACTIVE_REQUIRES_VERIFICATION"
    sale_mode = "AUCTION" if auction_terms else "SALE_MODE_REQUIRES_VERIFICATION"
    inventory_focus = (
        "MIXED_LOT_INCLUDES_CLOTHING"
        if any(term in combined.casefold() for term in ("mixed goods", "and more", "including"))
        else "CLOTHING_OR_FOOTWEAR_FOCUSED"
    )
    stock_location = _extract_location(combined)
    end_match = _END_TEXT_RE.search(combined)
    auction_end_text = _compact(end_match.group("value"))[:100] if end_match else None

    missing_information: list[str] = []
    if quantity is None and lot_units is None:
        missing_information.append("QUANTITY_OR_LOT_UNITS")
    if total_price is None or currency is None:
        missing_information.append("CURRENT_BID_OR_VISIBLE_PRICE")
    if not manifest_available:
        missing_information.append("MANIFEST_OR_ITEMISED_CONTENTS")
    if not condition_terms:
        missing_information.append("CONDITION")
    if not stock_location:
        missing_information.append("WAREHOUSE_LOCATION")
    if not shipping_terms:
        missing_information.append("SHIPPING_TO_NORWAY")
    if brands and not authenticity_terms:
        missing_information.append("BRAND_AUTHENTICITY_EVIDENCE")
    if listing_status != "ENDED" and not auction_end_text:
        missing_information.append("AUCTION_END_TIME")

    opportunity_state = (
        "B2B_LEAD_REQUIRES_VERIFICATION"
        if page_role == "SPECIFIC_AUCTION_OR_JOB_LOT"
        and listing_status != "ENDED"
        and len(missing_information) <= 3
        else "EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION"
    )

    score = 42
    score += 10 if quantity is not None or lot_units is not None else 0
    score += 10 if total_price is not None and currency else 0
    score += 9 if manifest_available else 0
    score += 6 if estimated_retail_value is not None else 0
    score += 6 if condition_terms else 0
    score += 5 if brands else 0
    score += 4 if shipping_terms else 0
    score += 4 if stock_location else 0
    score += 3 if auction_end_text else 0
    score += 3 if page_role == "SPECIFIC_AUCTION_OR_JOB_LOT" else 0
    score -= 12 if listing_status == "ENDED" else 0
    score = max(0, min(100, score))

    candidate_id = "jobalots-clothing:" + sha256(
        canonical_url.encode("utf-8")
    ).hexdigest()[:24]
    return {
        "candidate_id": candidate_id,
        "feed_family": FEED_FAMILY,
        "source_name": SOURCE_NAME,
        "source_region": SOURCE_REGION,
        "source_country": None,
        "official_domain": (urlsplit(canonical_url).hostname or "").casefold(),
        "source_url": canonical_url,
        "source_reference": _lot_reference(combined, canonical_url),
        "title": title[:1000],
        "description": (description or title)[:1500],
        "observed_at": _iso_utc(observed_at),
        "search_provider": _compact(hit.provider) or None,
        "page_role": page_role,
        "listing_status": listing_status,
        "sale_mode": sale_mode,
        "inventory_focus": inventory_focus,
        "clothing_terms": clothing_terms,
        "commercial_terms": commercial_terms,
        "auction_terms": auction_terms,
        "quantity": quantity,
        "quantity_unit": quantity_unit,
        "lot_units": lot_units,
        "lot_unit_type": lot_unit_type,
        "lot_size_band": _lot_size(quantity, quantity_unit, lot_units),
        "minimum_order": minimum_order,
        "minimum_order_unit": minimum_order_unit,
        "price_text": price_text,
        "unit_price": fallback_price if price_basis == "PER_UNIT" else None,
        "total_price": total_price,
        "current_bid": current_bid,
        "price_basis": price_basis,
        "currency": currency,
        "estimated_retail_value": estimated_retail_value,
        "estimated_retail_currency": rrp_currency,
        "condition_terms": condition_terms,
        "brands": brands,
        "stock_location": stock_location,
        "auction_end_text": auction_end_text,
        "manifest_available": manifest_available,
        "manifest_terms": manifest_terms,
        "unmanifested_terms": unmanifested_terms,
        "authenticity_evidence_visible": bool(authenticity_terms),
        "authenticity_terms": authenticity_terms,
        "shipping_information_present": bool(shipping_terms),
        "shipping_terms": shipping_terms,
        "seller_name": SOURCE_NAME,
        "seller_identity_status": "OFFICIAL_PLATFORM_REQUIRES_LOT_AND_LEGAL_VERIFICATION",
        "missing_information": missing_information,
        "opportunity_state": opportunity_state,
        "verification_status": "UNVERIFIED_OFFICIAL_DOMAIN_SEARCH_RESULT",
        "b2b_relevance_score": score,
        "decision_owner": "HUMAN_OPERATOR",
        "quantity_size_rejection_applied": False,
        "qualification_blockers": [
            "OPEN_AND_VERIFY_LIVE_LOT_PAGE",
            "VERIFY_AUCTION_STATUS_END_TIME_AND_BINDING_TERMS",
            "VERIFY_MANIFEST_QUANTITIES_CONDITION_AND_DEFECTS",
            "VERIFY_WAREHOUSE_LOCATION_AND_COLLECTION_OR_DELIVERY",
            "VERIFY_BRAND_AUTHENTICITY_AND_RESALE_RIGHTS",
            "CALCULATE_BID_FEES_FREIGHT_IMPORT_VAT_AND_LANDED_COST",
            *[f"MISSING_{item}" for item in missing_information],
        ],
        "recommended_operator_action": "OPEN_LOT_REVIEW_MANIFEST_CALCULATE_MAX_BID_AND_DECIDE_MANUALLY",
        **_safety_payload(),
    }, None


def jobalots_candidate_from_hit(
    hit: SearchHit,
    *,
    observed_at: datetime,
) -> dict[str, Any] | None:
    candidate, _ = _candidate_from_hit(hit, observed_at=observed_at)
    return candidate


def collect_jobalots_clothing_auction_feed(
    *,
    observed_at: datetime | None = None,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory = _default_provider_factory,
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
    freshness: str | None = DEFAULT_FRESHNESS,
) -> dict[str, Any]:
    if not 1 <= results_per_query <= MAX_RESULTS_PER_QUERY:
        raise ValueError(
            f"results_per_query must be between 1 and {MAX_RESULTS_PER_QUERY}"
        )

    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    env = environment if environment is not None else os.environ
    api_key = _compact(env.get("BRAVE_SEARCH_API_KEY")) or _compact(
        env.get("BRAVE_API_KEY")
    )

    source_report: dict[str, Any] = {
        "source_name": SOURCE_NAME,
        "source_region": SOURCE_REGION,
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
        source_report.update(
            status="BLOCKED_CONFIGURATION",
            block_reason="BRAVE_SEARCH_API_KEY_MISSING",
        )
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
                    source_report["errors"].append(
                        f"{type(exc).__name__}: {_compact(exc)[:300]}"
                    )
                    continue
                for hit in hits:
                    try:
                        canonical_url = _canonical_url(
                            _compact(getattr(hit, "url", ""))
                        )
                    except ValueError:
                        canonical_url = ""
                    if canonical_url and canonical_url in seen_urls:
                        duplicates += 1
                        continue
                    if canonical_url:
                        seen_urls.add(canonical_url)
                    candidate, rejection = _candidate_from_hit(
                        hit,
                        observed_at=now,
                    )
                    if candidate is None:
                        reason = rejection or "REJECTED_BY_GATE"
                        rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
                        continue
                    accepted[candidate["candidate_id"]] = candidate

            selected = sorted(
                accepted.values(),
                key=lambda item: (
                    -int(item["b2b_relevance_score"]),
                    str(item["source_url"]),
                ),
            )[:MAX_ACCEPTED]
            source_report.update(
                accepted_candidate_count=len(selected),
                rejected_result_count=sum(rejection_counts.values()),
                duplicate_result_count=duplicates,
                rejection_reason_counts=dict(sorted(rejection_counts.items())),
                candidates=selected,
                status=(
                    "SUCCESS"
                    if selected
                    else "VALID_ZERO"
                    if source_report["queries_succeeded"]
                    else "BLOCKED_RETRIEVAL"
                ),
                block_reason=(
                    None
                    if source_report["queries_succeeded"]
                    else "ALL_SEARCH_REQUESTS_FAILED"
                ),
            )

    status = _compact(source_report.get("status")).upper() or "UNKNOWN"
    candidates = source_report.get("candidates") or []
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso_utc(now),
        "feed_family": FEED_FAMILY,
        "purpose": "OFFICIAL_JOBLOT_CLOTHING_AUCTION_DECISION_SUPPORT",
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
        "operator_rule": "SURFACE_CLOTHING_JOB_LOTS_CALCULATE_MAX_BID_AND_LEAVE_DECISION_TO_HUMAN",
        "incomplete_signals_preserved": True,
        "ended_lots_preserved": True,
        "unmanifested_lots_preserved": True,
        "quantity_size_rejection_enabled": False,
        "human_decision_required": True,
        "not_part_of_opportunity_top5": True,
        **_safety_payload(),
    }
