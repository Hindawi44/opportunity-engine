"""Bounded official-domain marketplace watch for Merkandi clothing stock.

The feed preserves serious B2B listings even when public search snippets omit
commercial fields. Missing information lowers readiness and remains visible for
human verification. Lot size is descriptive only; it never rejects a listing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import os
import re
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit

from opportunity_engine.discovery.brave_market_signal_radar import (
    _canonical_url,
    _compact,
    _default_provider_factory,
    _iso_utc,
)
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider

SCHEMA_VERSION = "merkandi-b2b-liquidation-feed-1.1"
FEED_FAMILY = "MERKANDI_B2B_LIQUIDATION_FEED_V1"
SOURCE_NAME = "Merkandi"
SOURCE_DOMAIN = "merkandi.com"
SEARCH_REGION = "DE"
SEARCH_LANGUAGE = "en"
DEFAULT_RESULTS = 10
MAX_RESULTS = 10
MAX_ACCEPTED = 8
DEFAULT_FRESHNESS = "pm"
QUERY = (
    'site:merkandi.com ("clothing stock" OR "clothes stock" OR apparel OR garments) '
    '(wholesale OR stocklot OR "stock lot" OR liquidation OR clearance OR surplus '
    'OR overstock OR closeout OR "job lot") '
    '(quantity OR pcs OR pieces OR units OR kg OR MOQ OR "minimum order")'
)

ProviderFactory = Callable[[str, str, str | None], SearchProvider]

_CLOTHING_TERMS = (
    "clothing", "clothes", "apparel", "garment", "garments", "dress", "dresses",
    "jacket", "jackets", "coat", "coats", "trousers", "pants", "jeans", "shirt",
    "shirts", "blouse", "blouses", "skirt", "skirts", "sportswear", "workwear",
    "underwear", "textile stock", "fashion stock",
)
_COMMERCIAL_TERMS = (
    "wholesale", "stocklot", "stock lot", "liquidation", "clearance", "surplus",
    "overstock", "closeout", "bankrupt stock", "bankruptcy stock", "job lot",
    "warehouse stock", "outlet stock", "bulk",
)
_CONDITION_TERMS = (
    "new with tags", "new without tags", "customer returns", "grade a", "grade b",
    "outlet", "new", "used", "mixed condition",
)
_MANIFEST_TERMS = (
    "manifest", "packing list", "inventory list", "stock list", "itemized list",
    "itemised list",
)
_AUTHENTICITY_TERMS = (
    "certificate of authenticity", "proof of authenticity", "authentic goods",
    "authentic merchandise", "original invoice", "brand authorization",
    "brand authorisation", "100% original", "original stock",
)
_SHIPPING_TERMS = (
    "shipping", "delivery", "transport", "export", "freight", "ships to norway",
    "shipping to norway", "worldwide delivery",
)
_PRIVATE_SINGLE_TERMS = (
    "private seller", "single item", "one piece only", "personal sale",
)

_NUMBER_UNIT = (
    r"(?P<amount>\d{1,9}(?:[\s.,]\d{3})*(?:[.,]\d{1,2})?)\s*"
    r"(?P<unit>pcs?|pieces?|units?|items?|pairs?|sets?|kg|kilograms?)"
)
_QUANTITY_RE = re.compile(_NUMBER_UNIT, re.IGNORECASE)
_MOQ_RE = re.compile(
    rf"\b(?:minimum\s+(?:order|purchase)|moq|min\.?\s*order)\s*"
    rf"(?:is|of|:|-)?\s*{_NUMBER_UNIT}", re.IGNORECASE,
)
_PRICE_RE = re.compile(
    r"(?P<symbol>€|£|\$)\s?(?P<amount>\d{1,9}(?:[\s.,]\d{3})*(?:[.,]\d{1,2})?)"
    r"|(?P<amount2>\d{1,9}(?:[\s.,]\d{3})*(?:[.,]\d{1,2})?)\s?"
    r"(?P<code>EUR|GBP|USD|PLN|NOK|SEK|DKK)", re.IGNORECASE,
)
_SELLER_RE = re.compile(
    r"\b(?:seller|supplier|company|wholesaler)\s*(?:name)?\s*[:\-]\s*"
    r"(?P<name>[A-Za-z0-9][^|;\n]{2,80})", re.IGNORECASE,
)
_BRANDS_RE = re.compile(
    r"\bbrands?\s*[:\-]\s*(?P<brands>[^|;\n.]{2,160})", re.IGNORECASE,
)
_LOCATION_RE = re.compile(
    r"\b(?:stock\s+country|warehouse\s+country|warehouse\s+location|location)\s*"
    r"[:\-]\s*(?P<location>[A-Za-z][A-Za-z .'-]{2,60})", re.IGNORECASE,
)


def _safety_payload() -> dict[str, bool]:
    return {
        "promotion_to_opportunity_allowed": False,
        "analysis_eligible": False,
        "top5_eligible": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _official_domain(url: str, approved_domains: Sequence[str] = (SOURCE_DOMAIN,)) -> bool:
    host = (urlsplit(url).hostname or "").casefold().rstrip(".")
    return any(host == domain or host.endswith(f".{domain}") for domain in approved_domains)


def _matched_terms(text: str, terms: Sequence[str]) -> list[str]:
    folded = text.casefold()
    return sorted({term for term in terms if term.casefold() in folded})


def _parse_number(raw: str) -> float | None:
    value = re.sub(r"\s+", "", raw)
    if not value:
        return None
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif value.count(",") == 1:
        tail = value.rsplit(",", 1)[1]
        value = value.replace(",", "") if len(tail) == 3 else value.replace(",", ".")
    elif value.count(".") == 1:
        tail = value.rsplit(".", 1)[1]
        if len(tail) == 3:
            value = value.replace(".", "")
    else:
        value = value.replace(",", "").replace(".", "")
    try:
        return float(value)
    except ValueError:
        return None


def _normalize_unit(raw: str) -> str:
    unit = raw.casefold().rstrip(".")
    if unit in {"pc", "pcs", "piece", "pieces", "unit", "units", "item", "items"}:
        return "units"
    if unit in {"pair", "pairs"}:
        return "pairs"
    if unit in {"set", "sets"}:
        return "sets"
    return "kg"


def _extract_moq(text: str) -> tuple[float | None, str | None, tuple[int, int] | None]:
    match = _MOQ_RE.search(text)
    if not match:
        return None, None, None
    amount = _parse_number(match.group("amount"))
    return amount, _normalize_unit(match.group("unit")), match.span()


def _extract_inventory_quantity(
    text: str, *, moq_span: tuple[int, int] | None,
) -> tuple[float | None, str | None]:
    for match in _QUANTITY_RE.finditer(text):
        if moq_span and match.start() >= moq_span[0] and match.end() <= moq_span[1]:
            continue
        prefix = text[max(0, match.start() - 28):match.start()].casefold()
        if "minimum order" in prefix or "min. order" in prefix or "moq" in prefix:
            continue
        amount = _parse_number(match.group("amount"))
        if amount is not None:
            return amount, _normalize_unit(match.group("unit"))
    return None, None


def _extract_price(text: str) -> tuple[str | None, float | None, str | None, str | None]:
    match = _PRICE_RE.search(text)
    if not match:
        return None, None, None, None
    amount = _parse_number(match.group("amount") or match.group("amount2") or "")
    if amount is None:
        return None, None, None, None
    symbol = match.group("symbol")
    code = (match.group("code") or "").upper()
    currency = {"€": "EUR", "£": "GBP", "$": "USD"}.get(symbol or "", code or None)
    context = text[match.end():match.end() + 32].casefold()
    basis = "PER_UNIT" if re.search(r"(?:/|per\s+)(?:pc|piece|unit|item|kg)", context) else "UNSPECIFIED"
    return match.group(0), amount, currency, basis


def _extract_seller(text: str) -> str | None:
    match = _SELLER_RE.search(text)
    if not match:
        return None
    name = _compact(match.group("name"))
    name = re.split(r"\s{2,}|\.(?:\s|$)", name, maxsplit=1)[0].strip(" ,.-")
    return name[:120] if len(name) >= 3 else None


def _extract_brands(text: str) -> list[str]:
    match = _BRANDS_RE.search(text)
    if not match:
        return []
    return [
        item.strip(" ,.-")[:80]
        for item in re.split(r"[,/]", match.group("brands"))
        if len(item.strip(" ,.-")) >= 2
    ][:12]


def _extract_location(text: str) -> str | None:
    match = _LOCATION_RE.search(text)
    return _compact(match.group("location")).strip(" ,.-")[:80] if match else None


def _lot_size_band(quantity: float | None, unit: str | None) -> str:
    if quantity is None or unit is None:
        return "UNKNOWN"
    thresholds = (50, 500, 5_000) if unit == "kg" else (100, 1_000, 10_000)
    if quantity <= thresholds[0]:
        return "SMALL"
    if quantity <= thresholds[1]:
        return "MEDIUM"
    if quantity <= thresholds[2]:
        return "LARGE"
    return "VERY_LARGE"


def _evaluate_hit(hit: SearchHit, *, observed_at: datetime) -> tuple[dict[str, Any] | None, str | None]:
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
    if not _official_domain(canonical_url):
        return None, "UNAPPROVED_DOMAIN"
    if urlsplit(canonical_url).path in {"", "/"}:
        return None, "GENERIC_MARKETPLACE_HOME_PAGE"

    combined = f"{title} {description}".strip()
    clothing_terms = _matched_terms(combined, _CLOTHING_TERMS)
    commercial_terms = _matched_terms(combined, _COMMERCIAL_TERMS)
    if not clothing_terms:
        return None, "NOT_CLOTHING_INVENTORY"
    if not commercial_terms:
        return None, "NO_B2B_LIQUIDATION_SIGNAL"
    if _matched_terms(combined, _PRIVATE_SINGLE_TERMS):
        return None, "PRIVATE_OR_SINGLE_ITEM_LISTING"

    moq, moq_unit, moq_span = _extract_moq(combined)
    quantity, quantity_unit = _extract_inventory_quantity(combined, moq_span=moq_span)
    if quantity is not None and quantity <= 1:
        return None, "SINGLE_ITEM_LISTING"
    price_text, price, currency, price_basis = _extract_price(combined)
    seller_name = _extract_seller(combined)
    manifest_terms = _matched_terms(combined, _MANIFEST_TERMS)
    brands = _extract_brands(combined)
    authenticity_terms = _matched_terms(combined, _AUTHENTICITY_TERMS)
    condition_terms = _matched_terms(combined, _CONDITION_TERMS)
    shipping_terms = _matched_terms(combined, _SHIPPING_TERMS)
    stock_location = _extract_location(combined)

    missing_information: list[str] = []
    if quantity is None:
        missing_information.append("QUANTITY")
    if moq is None:
        missing_information.append("MINIMUM_ORDER")
    if price is None or currency is None:
        missing_information.append("VISIBLE_PRICE")
    if not seller_name:
        missing_information.append("SELLER_IDENTITY")
    if not manifest_terms:
        missing_information.append("MANIFEST_OR_PACKING_LIST")
    if brands and not authenticity_terms:
        missing_information.append("BRAND_AUTHENTICITY_EVIDENCE")

    opportunity_state = (
        "B2B_LEAD_REQUIRES_VERIFICATION"
        if not missing_information
        else "EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION"
    )
    score = 40
    score += 10 if quantity is not None else 0
    score += 8 if moq is not None else 0
    score += 10 if price is not None and currency else 0
    score += 8 if seller_name else 0
    score += 8 if manifest_terms else 0
    score += 6 if authenticity_terms else 0
    score += 4 if condition_terms else 0
    score += 3 if shipping_terms else 0
    score += 3 if stock_location else 0
    score = min(100, score)

    candidate_id = f"merkandi-b2b:{sha256(canonical_url.encode('utf-8')).hexdigest()[:24]}"
    return {
        "candidate_id": candidate_id,
        "feed_family": FEED_FAMILY,
        "source_name": SOURCE_NAME,
        "official_domain": SOURCE_DOMAIN,
        "source_url": canonical_url,
        "title": title[:1000],
        "description": (description or title)[:1500],
        "observed_at": _iso_utc(observed_at),
        "search_provider": _compact(hit.provider) or None,
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
        "seller_name": seller_name,
        "seller_identity_status": (
            "NAMED_UNVERIFIED_MARKETPLACE_SELLER" if seller_name else "MISSING_REQUIRES_VERIFICATION"
        ),
        "missing_information": missing_information,
        "opportunity_state": opportunity_state,
        "verification_status": "UNVERIFIED_MARKETPLACE_SEARCH_RESULT",
        "b2b_relevance_score": score,
        "operator_fit": "HUMAN_DECISION_REQUIRED_NO_SIZE_REJECTION",
        "decision_owner": "HUMAN_OPERATOR",
        "quantity_size_rejection_applied": False,
        "qualification_blockers": [
            "VERIFY_LISTING_ACTIVE_ON_SOURCE_PAGE",
            "VERIFY_SELLER_LEGAL_IDENTITY",
            "VERIFY_MANIFEST_CONTENTS",
            "VERIFY_AUTHENTICITY_WHEN_BRANDED",
            "VERIFY_SHIPPING_TO_NORWAY",
            "VERIFY_IMPORT_VAT_CUSTOMS_AND_TOTAL_LANDED_COST",
            *[f"MISSING_{item}" for item in missing_information],
        ],
        "recommended_operator_action": "OPEN_SOURCE_PAGE_COLLECT_MISSING_DATA_CALCULATE_AND_DECIDE",
        **_safety_payload(),
    }, None


def merkandi_candidate_from_hit(hit: SearchHit, *, observed_at: datetime) -> dict[str, Any] | None:
    candidate, _ = _evaluate_hit(hit, observed_at=observed_at)
    return candidate


def collect_merkandi_b2b_liquidation_feed(
    *,
    observed_at: datetime | None = None,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory = _default_provider_factory,
    results: int = DEFAULT_RESULTS,
    freshness: str | None = DEFAULT_FRESHNESS,
) -> dict[str, Any]:
    if not 1 <= results <= MAX_RESULTS:
        raise ValueError(f"results must be between 1 and {MAX_RESULTS}")
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    env = environment if environment is not None else os.environ
    api_key = _compact(env.get("BRAVE_SEARCH_API_KEY")) or _compact(env.get("BRAVE_API_KEY"))

    source_report: dict[str, Any] = {
        "source_name": SOURCE_NAME,
        "official_domain": SOURCE_DOMAIN,
        "query": QUERY,
        "search_region": SEARCH_REGION,
        "search_language": SEARCH_LANGUAGE,
        "query_budget": 1,
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
            source_report["queries_attempted"] = 1
            requests_made = 1
            hits = provider.search(QUERY, count=results)
            source_report["queries_succeeded"] = 1
        except Exception as exc:
            source_report.update(
                status="BLOCKED_RETRIEVAL",
                block_reason="SEARCH_REQUEST_FAILED",
                errors=[f"{type(exc).__name__}: {_compact(exc)[:300]}"],
            )
        else:
            accepted: dict[str, dict[str, Any]] = {}
            seen_urls: set[str] = set()
            rejection_counts: dict[str, int] = {}
            duplicates = 0
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
                candidate, rejection = _evaluate_hit(hit, observed_at=now)
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
                status="SUCCESS" if selected else "VALID_ZERO",
                block_reason=None,
            )

    status = _compact(source_report.get("status")).upper() or "UNKNOWN"
    candidates = source_report.get("candidates") or []
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso_utc(now),
        "feed_family": FEED_FAMILY,
        "purpose": "B2B_CLOTHING_LIQUIDATION_DECISION_SUPPORT",
        "approved_official_domains": [SOURCE_DOMAIN],
        "source_count": 1,
        "query_budget_total": 1,
        "requests_made": requests_made,
        "results_requested": results,
        "freshness": freshness,
        "status_counts": {status: 1},
        "candidate_count": len(candidates),
        "candidates": candidates,
        "sources": [source_report],
        "operator_rule": "SURFACE_EVIDENCE_CALCULATE_AND_LEAVE_FINAL_DECISION_TO_HUMAN",
        "incomplete_signals_preserved": True,
        "quantity_size_rejection_enabled": False,
        "human_decision_required": True,
        "not_part_of_opportunity_top5": True,
        **_safety_payload(),
    }
