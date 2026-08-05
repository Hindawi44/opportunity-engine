"""Bounded official-domain marketplace watch for verified Merkandi stock lots.

The feed is intentionally conservative. It surfaces only marketplace search results
that expose enough commercial evidence to justify human review: clothing stock,
quantity, minimum order, visible price, named seller, and a manifest or packing
list. Results remain unverified B2B leads and never trigger contact, bidding,
purchase, payment, Top 5 promotion, or financial analysis.
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


SCHEMA_VERSION = "merkandi-b2b-liquidation-feed-1.0"
FEED_FAMILY = "MERKANDI_B2B_LIQUIDATION_FEED_V1"
SOURCE_NAME = "Merkandi"
SOURCE_DOMAIN = "merkandi.com"
SEARCH_REGION = "DE"
SEARCH_LANGUAGE = "en"
DEFAULT_RESULTS = 10
MAX_RESULTS = 10
MAX_ACCEPTED = 5
DEFAULT_FRESHNESS = "pm"
MAX_SMALL_OPERATOR_UNITS = 5_000
MAX_SMALL_OPERATOR_KG = 1_000
QUERY = (
    'site:merkandi.com ("clothing stock" OR "clothes stock" OR apparel OR garments) '
    '(wholesale OR stocklot OR "stock lot" OR liquidation OR clearance OR surplus '
    'OR overstock OR closeout OR "job lot") '
    '(quantity OR pcs OR pieces OR units OR kg OR MOQ OR "minimum order")'
)

ProviderFactory = Callable[[str, str, str | None], SearchProvider]

_CLOTHING_TERMS = (
    "clothing",
    "clothes",
    "apparel",
    "garment",
    "garments",
    "dress",
    "dresses",
    "jacket",
    "jackets",
    "coat",
    "coats",
    "trousers",
    "pants",
    "jeans",
    "shirt",
    "shirts",
    "blouse",
    "blouses",
    "skirt",
    "skirts",
    "sportswear",
    "workwear",
    "underwear",
    "textile stock",
)
_COMMERCIAL_TERMS = (
    "wholesale",
    "stocklot",
    "stock lot",
    "liquidation",
    "clearance",
    "surplus",
    "overstock",
    "closeout",
    "bankrupt stock",
    "bankruptcy stock",
    "job lot",
    "warehouse stock",
    "outlet stock",
)
_CONDITION_TERMS = (
    "new with tags",
    "new without tags",
    "customer returns",
    "grade a",
    "grade b",
    "outlet",
    "new",
    "used",
    "mixed condition",
)
_MANIFEST_TERMS = (
    "manifest",
    "packing list",
    "inventory list",
    "stock list",
    "itemized list",
    "itemised list",
)
_AUTHENTICITY_TERMS = (
    "certificate of authenticity",
    "proof of authenticity",
    "authentic goods",
    "authentic merchandise",
    "original invoice",
    "brand authorization",
    "brand authorisation",
)
_SHIPPING_TERMS = (
    "shipping",
    "delivery",
    "transport",
    "export",
    "freight",
    "ships to norway",
    "shipping to norway",
)
_PRIVATE_SINGLE_TERMS = (
    "private seller",
    "single item",
    "one piece only",
    "personal sale",
)

_NUMBER_UNIT = (
    r"(?P<amount>\d{1,9}(?:[\s.,]\d{3})*(?:[.,]\d{1,2})?)\s*"
    r"(?P<unit>pcs?|pieces?|units?|items?|pairs?|sets?|kg|kilograms?)"
)
_QUANTITY_RE = re.compile(_NUMBER_UNIT, re.IGNORECASE)
_MOQ_RE = re.compile(
    rf"\b(?:minimum\s+(?:order|purchase)|moq|min\.?\s*order)\s*"
    rf"(?:is|of|:|-)?\s*{_NUMBER_UNIT}",
    re.IGNORECASE,
)
_PRICE_RE = re.compile(
    r"(?P<symbol>€|£|\$)\s?(?P<amount>\d{1,9}(?:[\s.,]\d{3})*(?:[.,]\d{1,2})?)"
    r"|(?P<amount2>\d{1,9}(?:[\s.,]\d{3})*(?:[.,]\d{1,2})?)\s?"
    r"(?P<code>EUR|GBP|USD|PLN|NOK|SEK|DKK)",
    re.IGNORECASE,
)
_SELLER_RE = re.compile(
    r"\b(?:seller|supplier|company|wholesaler)\s*(?:name)?\s*[:\-]\s*"
    r"(?P<name>[A-Za-z0-9][^|;\n]{2,80})",
    re.IGNORECASE,
)
_BRANDS_RE = re.compile(
    r"\bbrands?\s*[:\-]\s*(?P<brands>[^|;\n.]{2,120})",
    re.IGNORECASE,
)
_LOCATION_RE = re.compile(
    r"\b(?:stock\s+country|warehouse\s+country|warehouse\s+location|location)\s*"
    r"[:\-]\s*(?P<location>[A-Za-z][A-Za-z .'-]{2,40})",
    re.IGNORECASE,
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


def _official_domain(url: str) -> bool:
    host = (urlsplit(url).hostname or "").casefold().rstrip(".")
    return host == SOURCE_DOMAIN or host.endswith(f".{SOURCE_DOMAIN}")


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
    if amount is None:
        return None, None, match.span()
    return amount, _normalize_unit(match.group("unit")), match.span()


def _extract_inventory_quantity(
    text: str,
    *,
    moq_span: tuple[int, int] | None,
) -> tuple[float | None, str | None]:
    for match in _QUANTITY_RE.finditer(text):
        if moq_span and match.start() >= moq_span[0] and match.end() <= moq_span[1]:
            continue
        prefix = text[max(0, match.start() - 28) : match.start()].casefold()
        if "minimum order" in prefix or "min. order" in prefix or "moq" in prefix:
            continue
        amount = _parse_number(match.group("amount"))
        if amount is None:
            continue
        return amount, _normalize_unit(match.group("unit"))
    return None, None


def _extract_price(text: str) -> tuple[str | None, float | None, str | None, str | None]:
    match = _PRICE_RE.search(text)
    if not match:
        return None, None, None, None
    raw_amount = match.group("amount") or match.group("amount2")
    if not raw_amount:
        return None, None, None, None
    amount = _parse_number(raw_amount)
    if amount is None:
        return None, None, None, None
    symbol = match.group("symbol")
    code = (match.group("code") or "").upper()
    currency = {"€": "EUR", "£": "GBP", "$": "USD"}.get(symbol or "", code or None)
    context = text[match.end() : match.end() + 32].casefold()
    basis = "PER_UNIT" if re.search(r"(?:/|per\s+)(?:pc|piece|unit|item|kg)", context) else "UNSPECIFIED"
    return match.group(0), amount, currency, basis


def _extract_seller(text: str) -> str | None:
    match = _SELLER_RE.search(text)
    if not match:
        return None
    name = _compact(match.group("name"))
    name = re.split(r"\s{2,}|\.(?:\s|$)", name, maxsplit=1)[0].strip(" ,.-")
    if len(name) < 3:
        return None
    return name[:120]


def _extract_brands(text: str) -> list[str]:
    match = _BRANDS_RE.search(text)
    if not match:
        return []
    raw = match.group("brands")
    return [
        item.strip(" ,.-")[:80]
        for item in re.split(r"[,/]", raw)
        if len(item.strip(" ,.-")) >= 2
    ][:12]


def _extract_location(text: str) -> str | None:
    match = _LOCATION_RE.search(text)
    if not match:
        return None
    return _compact(match.group("location")).strip(" ,.-")[:80] or None


def _operator_quantity_fit(quantity: float, unit: str) -> bool:
    if unit == "kg":
        return quantity <= MAX_SMALL_OPERATOR_KG
    return quantity <= MAX_SMALL_OPERATOR_UNITS


def _evaluate_hit(
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
    if quantity is None or quantity_unit is None:
        return None, "QUANTITY_MISSING"
    if quantity <= 1:
        return None, "SINGLE_ITEM_LISTING"
    if not _operator_quantity_fit(quantity, quantity_unit):
        return None, "QUANTITY_ABOVE_SMALL_OPERATOR_LIMIT"
    if moq is None or moq_unit is None:
        return None, "MINIMUM_ORDER_MISSING"

    price_text, price, currency, price_basis = _extract_price(combined)
    if price is None or currency is None:
        return None, "VISIBLE_PRICE_MISSING"

    seller_name = _extract_seller(combined)
    if not seller_name:
        return None, "SELLER_IDENTITY_MISSING"

    manifest_terms = _matched_terms(combined, _MANIFEST_TERMS)
    if not manifest_terms:
        return None, "MANIFEST_OR_PACKING_LIST_MISSING"

    brands = _extract_brands(combined)
    authenticity_terms = _matched_terms(combined, _AUTHENTICITY_TERMS)
    if brands and not authenticity_terms:
        return None, "BRANDED_WITHOUT_AUTHENTICITY_EVIDENCE"

    condition_terms = _matched_terms(combined, _CONDITION_TERMS)
    shipping_terms = _matched_terms(combined, _SHIPPING_TERMS)
    score = 55
    score += 10 if condition_terms else 0
    score += 10 if authenticity_terms else 0
    score += 10 if shipping_terms else 0
    score += 5 if brands else 0
    score += 10 if _extract_location(combined) else 0
    score = min(100, score)

    candidate_id = (
        "merkandi-b2b:"
        f"{sha256(canonical_url.encode('utf-8')).hexdigest()[:24]}"
    )
    unit_price = price if price_basis == "PER_UNIT" else None
    total_price = price if price_basis != "PER_UNIT" else None
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
        "minimum_order": moq,
        "minimum_order_unit": moq_unit,
        "price_text": price_text,
        "unit_price": unit_price,
        "total_price": total_price,
        "price_basis": price_basis,
        "currency": currency,
        "condition_terms": condition_terms,
        "brands": brands,
        "stock_location": _extract_location(combined),
        "manifest_available": True,
        "manifest_terms": manifest_terms,
        "authenticity_evidence_visible": bool(authenticity_terms),
        "authenticity_terms": authenticity_terms,
        "shipping_information_present": bool(shipping_terms),
        "shipping_terms": shipping_terms,
        "seller_name": seller_name,
        "seller_identity_status": "NAMED_UNVERIFIED_MARKETPLACE_SELLER",
        "opportunity_state": "B2B_LEAD_REQUIRES_VERIFICATION",
        "verification_status": "UNVERIFIED_MARKETPLACE_SEARCH_RESULT",
        "b2b_relevance_score": score,
        "operator_fit": "SMALL_OPERATOR_QUANTITY_GATE_PASSED",
        "qualification_blockers": [
            "VERIFY_LISTING_ACTIVE_ON_SOURCE_PAGE",
            "VERIFY_SELLER_LEGAL_IDENTITY",
            "VERIFY_MANIFEST_CONTENTS",
            "VERIFY_AUTHENTICITY_WHEN_BRANDED",
            "VERIFY_SHIPPING_TO_NORWAY",
            "VERIFY_IMPORT_VAT_CUSTOMS_AND_TOTAL_LANDED_COST",
        ],
        "recommended_operator_action": "OPEN_SOURCE_PAGE_AND_VERIFY_SELLER_MANIFEST_AND_LANDED_COST",
        **_safety_payload(),
    }, None


def merkandi_candidate_from_hit(
    hit: SearchHit,
    *,
    observed_at: datetime,
) -> dict[str, Any] | None:
    """Normalize one official Merkandi result into a strict review-only B2B lead."""
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
    """Run one bounded official-domain search for strict Merkandi B2B leads."""
    if not 1 <= results <= MAX_RESULTS:
        raise ValueError(f"results must be between 1 and {MAX_RESULTS}")

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
        source_report["status"] = "BLOCKED_CONFIGURATION"
        source_report["block_reason"] = "BRAVE_SEARCH_API_KEY_MISSING"
    else:
        try:
            provider = provider_factory(SEARCH_REGION, api_key, freshness)
        except Exception as exc:
            source_report["status"] = "BLOCKED_RETRIEVAL"
            source_report["block_reason"] = "PROVIDER_INITIALIZATION_FAILED"
            source_report["errors"] = [f"{type(exc).__name__}: {_compact(exc)[:300]}"]
        else:
            source_report["queries_attempted"] = 1
            requests_made = 1
            try:
                hits = provider.search(QUERY, count=results)
                source_report["queries_succeeded"] = 1
            except Exception as exc:
                source_report["status"] = "BLOCKED_RETRIEVAL"
                source_report["block_reason"] = "SEARCH_REQUEST_FAILED"
                source_report["errors"] = [f"{type(exc).__name__}: {_compact(exc)[:300]}"]
            else:
                accepted: dict[str, dict[str, Any]] = {}
                seen_urls: set[str] = set()
                rejection_counts: dict[str, int] = {}
                duplicates = 0
                for hit in hits:
                    if not isinstance(hit, SearchHit):
                        rejection_counts["INVALID_SEARCH_HIT"] = (
                            rejection_counts.get("INVALID_SEARCH_HIT", 0) + 1
                        )
                        continue
                    try:
                        canonical_url = _canonical_url(_compact(hit.url))
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
                source_report["accepted_candidate_count"] = len(selected)
                source_report["rejected_result_count"] = sum(rejection_counts.values())
                source_report["duplicate_result_count"] = duplicates
                source_report["rejection_reason_counts"] = dict(sorted(rejection_counts.items()))
                source_report["candidates"] = selected
                source_report["status"] = "SUCCESS" if selected else "VALID_ZERO"
                source_report["block_reason"] = None

    status = _compact(source_report.get("status")).upper() or "UNKNOWN"
    candidates = source_report.get("candidates") or []
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso_utc(now),
        "feed_family": FEED_FAMILY,
        "purpose": "SMALL_OPERATOR_B2B_CLOTHING_LIQUIDATION_INTELLIGENCE",
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
        "operator_rule": "VERIFY_SELLER_MANIFEST_AUTHENTICITY_SHIPPING_AND_LANDED_COST_BEFORE_CONTACT",
        "seller_identity_required": True,
        "quantity_required": True,
        "minimum_order_required": True,
        "visible_price_required": True,
        "manifest_required": True,
        "small_operator_quantity_limit_units": MAX_SMALL_OPERATOR_UNITS,
        "small_operator_quantity_limit_kg": MAX_SMALL_OPERATOR_KG,
        "not_part_of_opportunity_top5": True,
        **_safety_payload(),
    }
