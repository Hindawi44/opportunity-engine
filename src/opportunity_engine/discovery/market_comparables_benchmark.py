"""Bounded public-market comparables for the unified actionable lane.

This module benchmarks at most three actionable intelligence items against
public search-result evidence. It does not estimate shipping, assume an FX
rate, open seller accounts, contact anyone, bid, reserve, purchase, or pay.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from statistics import median
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

from opportunity_engine.discovery.brave_market_signal_radar import _default_provider_factory
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider

SCHEMA_VERSION = "market-comparables-benchmark-1.0"
FEED_FAMILY = "MARKET_COMPARABLES_BENCHMARK_V1"
OUTPUT_FILENAME = "market-comparables-benchmark.json"
MAX_TARGETS = 3
QUERIES_PER_TARGET = 2
RESULTS_PER_QUERY = 5
MAX_COMPARABLES_PER_TARGET = 10
DEFAULT_FRESHNESS = "pm"
DECISION_OWNER = "HUMAN_OPERATOR"

ProviderFactory = Callable[[str, str, str | None], SearchProvider]

_PRICE_RE = re.compile(
    r"(?:(?P<c1>NOK|SEK|DKK|EUR|GBP|USD|PLN|kr|€|£|\$)\s*"
    r"(?P<a1>\d{1,9}(?:[\s.,]\d{3})*(?:[.,]\d{1,2})?)|"
    r"(?P<a2>\d{1,9}(?:[\s.,]\d{3})*(?:[.,]\d{1,2})?)\s*"
    r"(?P<c2>NOK|SEK|DKK|EUR|GBP|USD|PLN|kr|€|£|\$))",
    re.IGNORECASE,
)
_QUANTITY_RE = re.compile(
    r"\b(?P<n>\d{1,7}(?:[\s.,]\d{3})*)\s*"
    r"(?P<u>pcs?|pieces?|items?|stk|st\.?|kg|kilograms?|m|metres?|meters?)\b",
    re.IGNORECASE,
)
_PER_UNIT_RE = re.compile(
    r"(?:/|\bper\s+)(?P<u>pcs?|pieces?|items?|stk|st\.?|kg|kilograms?|m|metres?|meters?)\b",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"[a-z0-9à-öø-ÿ]{2,}", re.IGNORECASE)

_WHOLESALE_TERMS = {
    "wholesale", "bulk", "joblot", "job", "lot", "pallet", "stocklot",
    "clearance", "liquidation", "overstock", "engros", "parti", "restlager",
    "grosshandel", "restposten", "lager", "hurt", "hurtownia", "pakiet",
}
_GARMENT_TERMS = {
    "jacket", "jackets", "coat", "coats", "workwear", "coverall", "coveralls",
    "trousers", "pants", "dress", "dresses", "gown", "gowns", "shirt", "shirts",
    "shoe", "shoes", "footwear", "clothing", "apparel", "lace", "tulle", "fabric",
    "jakke", "jakker", "arbeidsklær", "arbeidsklaer", "kjeledress", "bukse", "bukser",
    "kjole", "kjoler", "klær", "klaer", "kläder", "jacka", "arbetskläder",
    "bekleidung", "jacke", "arbeitskleidung", "kleidung",
}
_STOPWORDS = {
    "and", "with", "the", "for", "from", "including", "more", "new", "used",
    "grade", "mix", "stock", "offer", "sale", "inventory", "official", "current",
    "stk", "pcs", "piece", "pieces", "item", "items", "kg", "lot", "pallet",
    "inkl", "med", "til", "av", "og", "fra", "klær", "klaer", "clothing",
}
_COUNTRY_CURRENCY = {
    "NO": "NOK", "SE": "SEK", "DK": "DKK", "DE": "EUR", "NL": "EUR",
    "FR": "EUR", "IT": "EUR", "ES": "EUR", "PL": "PLN", "GB": "GBP",
    "UK": "GBP", "US": "USD",
}
_QUERY_SUFFIXES = {
    "NO": {
        "WHOLESALE": "(engros OR parti OR restlager OR grossist) pris",
        "RETAIL": "(butikk OR nettbutikk OR brukt) pris",
    },
    "SE": {
        "WHOLESALE": "(grossist OR parti OR restlager) pris",
        "RETAIL": "(butik OR webbutik OR begagnad) pris",
    },
    "DE": {
        "WHOLESALE": "(Großhandel OR Restposten OR Warenbestand) Preis",
        "RETAIL": "(Shop OR gebraucht OR Einzelhandel) Preis",
    },
    "PL": {
        "WHOLESALE": "(hurt OR hurtownia OR pakiet) cena",
        "RETAIL": "(sklep OR detaliczna OR używane) cena",
    },
    "GB": {
        "WHOLESALE": "(wholesale OR job lot OR clearance) price",
        "RETAIL": "(shop OR retail OR used) price",
    },
}


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _parse_number(value: object) -> float | None:
    text = _compact(value).replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        decimal = "," if text.rfind(",") > text.rfind(".") else "."
        thousands = "." if decimal == "," else ","
        text = text.replace(thousands, "").replace(decimal, ".")
    elif "," in text:
        tail = text.rsplit(",", 1)[1]
        text = text.replace(",", "." if len(tail) <= 2 else "")
    elif "." in text:
        tail = text.rsplit(".", 1)[1]
        if len(tail) == 3:
            text = text.replace(".", "")
    try:
        return float(text)
    except ValueError:
        return None


def _canonical_url(value: object) -> str | None:
    raw = _compact(value)
    if not raw:
        return None
    try:
        parts = urlsplit(raw)
    except ValueError:
        return None
    if parts.scheme.casefold() not in {"http", "https"} or not parts.hostname:
        return None
    host = parts.hostname.casefold().rstrip(".")
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.casefold(), host, path, "", ""))


def _currency(raw: object, country: str) -> str | None:
    value = _compact(raw).upper()
    if value == "KR":
        return _COUNTRY_CURRENCY.get(country)
    return {"€": "EUR", "£": "GBP", "$": "USD"}.get(value, value or None)


def _unit(raw: object) -> str | None:
    value = _compact(raw).casefold().rstrip(".")
    if value in {"pc", "pcs", "piece", "pieces", "item", "items", "stk", "st"}:
        return "PER_ITEM"
    if value in {"kg", "kilogram", "kilograms"}:
        return "PER_KG"
    if value in {"m", "metre", "metres", "meter", "meters"}:
        return "PER_METRE"
    return None


def _tokens(value: object) -> set[str]:
    return {
        token.casefold()
        for token in _TOKEN_RE.findall(_compact(value))
        if token.casefold() not in _STOPWORDS and not token.isdigit()
    }


def _details(item: Mapping[str, Any]) -> Mapping[str, Any]:
    value = item.get("details")
    return value if isinstance(value, Mapping) else {}


def _item_richness(item: Mapping[str, Any]) -> tuple[int, float, str]:
    details = _details(item)
    fields = (
        "unit_price", "total_price", "current_bid", "price", "currency",
        "quantity", "quantity_unit", "brands", "grade", "manifest_available",
    )
    populated = sum(details.get(key) not in (None, "", [], {}) for key in fields)
    return populated, float(item.get("score") or 0.0), _compact(item.get("intelligence_id"))


def _target_basis(item: Mapping[str, Any]) -> str | None:
    details = _details(item)
    unit_hint = _unit(details.get("unit_hint") or details.get("minimum_order_unit"))
    if unit_hint:
        return unit_hint
    quantity_unit = _unit(details.get("quantity_unit"))
    if quantity_unit:
        return quantity_unit
    kind = _compact(item.get("record_kind")).upper()
    if kind == "FABRIC_PROCUREMENT_ITEM":
        return "PER_METRE"
    if _number(details.get("quantity")) is not None:
        return "PER_ITEM"
    return None


def _target_price(item: Mapping[str, Any], fx: Mapping[str, float]) -> dict[str, Any]:
    details = _details(item)
    country = _compact(item.get("source_country")).upper()
    currency = _currency(details.get("currency"), country) or _COUNTRY_CURRENCY.get(country)
    basis = _target_basis(item)
    amount = _number(details.get("unit_price"))
    source_field = "UNIT_PRICE" if amount is not None else None
    quantity = _number(details.get("quantity"))
    if amount is None:
        for field in ("total_price", "current_bid", "price"):
            total = _number(details.get(field))
            if total is None:
                continue
            source_field = field.upper()
            if quantity and quantity > 0 and basis in {"PER_ITEM", "PER_KG", "PER_METRE"}:
                amount = total / quantity
            else:
                amount = total
                basis = "TOTAL_OR_UNCLEAR"
            break
    nok = amount * fx[currency] if amount is not None and currency in fx else None
    return {
        "amount": round(amount, 4) if amount is not None else None,
        "currency": currency,
        "basis": basis,
        "amount_nok": round(nok, 4) if nok is not None else None,
        "source_field": source_field,
        "final_purchase_price": False,
    }


def select_benchmark_targets(
    brief: Mapping[str, Any],
    cases_report: Mapping[str, Any],
    items_report: Mapping[str, Any],
    *,
    max_targets: int = MAX_TARGETS,
) -> list[dict[str, Any]]:
    """Select one specific, evidence-rich item from each leading actionable case."""
    cards = brief.get("actionable_now") if isinstance(brief.get("actionable_now"), list) else []
    cases = cases_report.get("cases") if isinstance(cases_report.get("cases"), list) else []
    items = items_report.get("items") if isinstance(items_report.get("items"), list) else []
    case_by_id = {
        _compact(case.get("case_id")): case
        for case in cases
        if isinstance(case, Mapping) and _compact(case.get("case_id"))
    }
    item_by_id = {
        _compact(item.get("intelligence_id")): item
        for item in items
        if isinstance(item, Mapping) and _compact(item.get("intelligence_id"))
    }
    targets: list[dict[str, Any]] = []
    seen_items: set[str] = set()
    for card in cards:
        if not isinstance(card, Mapping):
            continue
        case_id = _compact(card.get("case_id"))
        case = case_by_id.get(case_id, {})
        item_ids = case.get("item_ids") if isinstance(case.get("item_ids"), list) else []
        candidates = [item_by_id.get(_compact(item_id)) for item_id in item_ids]
        candidates = [item for item in candidates if isinstance(item, Mapping)]
        if not candidates:
            continue
        chosen = max(candidates, key=_item_richness)
        item_id = _compact(chosen.get("intelligence_id"))
        if not item_id or item_id in seen_items:
            continue
        seen_items.add(item_id)
        targets.append(
            {
                "rank": len(targets) + 1,
                "case_id": case_id,
                "intelligence_id": item_id,
                "title": _compact(chosen.get("title") or card.get("headline")),
                "record_kind": _compact(chosen.get("record_kind")).upper(),
                "source_name": _compact(chosen.get("source_name")),
                "source_country": _compact(chosen.get("source_country")).upper() or "NO",
                "source_url": _canonical_url(chosen.get("source_url")),
                "seller_name": _compact(chosen.get("seller_name")) or None,
                "brands": [
                    _compact(value)
                    for value in (_details(chosen).get("brands") or [])
                    if _compact(value)
                ][:10],
                "details": dict(_details(chosen)),
                "actionability_score": card.get("actionability_score"),
                "priority_class": card.get("priority_class"),
            }
        )
        if len(targets) >= max_targets:
            break
    return targets


def _query_core(target: Mapping[str, Any]) -> str:
    title = _compact(target.get("title"))
    brands = [value for value in target.get("brands") or [] if _compact(value)]
    prefix = f'"{brands[0]}" ' if brands else ""
    words = [word for word in _TOKEN_RE.findall(title) if word.casefold() not in _STOPWORDS]
    core = " ".join(words[:10]) or title
    source_url = _canonical_url(target.get("source_url"))
    exclusion = f" -site:{urlsplit(source_url).hostname}" if source_url else ""
    return _compact(f"{prefix}{core}{exclusion}")


def build_comparable_queries(target: Mapping[str, Any]) -> list[dict[str, str]]:
    country = _compact(target.get("source_country")).upper()
    suffixes = _QUERY_SUFFIXES.get(country, _QUERY_SUFFIXES["GB"])
    core = _query_core(target)
    return [
        {"lane": "WHOLESALE", "query": _compact(f"{core} {suffixes['WHOLESALE']}")},
        {"lane": "RETAIL", "query": _compact(f"{core} {suffixes['RETAIL']}")},
    ]


def _similarity(target: Mapping[str, Any], hit: SearchHit) -> tuple[float, list[str]]:
    title_tokens = _tokens(target.get("title"))
    hit_tokens = _tokens(f"{hit.title} {hit.description}")
    overlap = title_tokens & hit_tokens
    base = min(70.0, 70.0 * len(overlap) / max(2, min(8, len(title_tokens))))
    reasons: list[str] = []
    brands = {_compact(value).casefold() for value in target.get("brands") or [] if _compact(value)}
    hit_text = _compact(f"{hit.title} {hit.description}").casefold()
    if brands and any(brand in hit_text for brand in brands):
        base += 20.0
        reasons.append("BRAND_MATCH")
    target_garments = title_tokens & _GARMENT_TERMS
    hit_garments = hit_tokens & _GARMENT_TERMS
    if target_garments and hit_garments and target_garments & hit_garments:
        base += 10.0
        reasons.append("GARMENT_TYPE_MATCH")
    if overlap:
        reasons.append("TITLE_TOKEN_OVERLAP")
    return round(min(100.0, base), 2), reasons


def _extract_price(text: str, country: str) -> tuple[float | None, str | None]:
    match = _PRICE_RE.search(text)
    if not match:
        return None, None
    amount = _parse_number(match.group("a1") or match.group("a2"))
    currency = _currency(match.group("c1") or match.group("c2"), country)
    return amount, currency


def _comparison_basis(text: str, lane: str, target_basis: str | None) -> tuple[str, float | None, str | None]:
    per_match = _PER_UNIT_RE.search(text)
    if per_match:
        return _unit(per_match.group("u")) or "TOTAL_OR_UNCLEAR", None, None
    quantity_match = _QUANTITY_RE.search(text)
    if quantity_match:
        quantity = _parse_number(quantity_match.group("n"))
        return _unit(quantity_match.group("u")) or "TOTAL_OR_UNCLEAR", quantity, "DIVIDE_TOTAL_BY_VISIBLE_QUANTITY"
    folded = text.casefold()
    if target_basis == "PER_METRE" and any(term in folded for term in ("per metre", "per meter", "/m", "metre", "meter")):
        return "PER_METRE", None, None
    if lane == "RETAIL" and not (_tokens(text) & _WHOLESALE_TERMS):
        return "PER_ITEM", None, "SINGLE_RETAIL_LISTING_ASSUMPTION"
    return "TOTAL_OR_UNCLEAR", None, None


def comparable_from_hit(
    *,
    target: Mapping[str, Any],
    hit: SearchHit,
    lane: str,
    fx_rates_to_nok: Mapping[str, float],
) -> tuple[dict[str, Any] | None, str | None]:
    url = _canonical_url(hit.url)
    if not url:
        return None, "INVALID_URL"
    if url == _canonical_url(target.get("source_url")):
        return None, "SOURCE_LISTING_SELF_MATCH"
    text = _compact(f"{hit.title} {hit.description}")
    amount, currency = _extract_price(text, _compact(target.get("source_country")).upper())
    if amount is None or not currency:
        return None, "VISIBLE_PRICE_MISSING"
    target_basis = _target_basis(target)
    basis, visible_quantity, basis_note = _comparison_basis(text, lane, target_basis)
    unit_amount = amount
    if visible_quantity and visible_quantity > 0 and basis in {"PER_ITEM", "PER_KG", "PER_METRE"}:
        unit_amount = amount / visible_quantity
    if basis != target_basis or basis not in {"PER_ITEM", "PER_KG", "PER_METRE"}:
        return None, "COMPARISON_UNIT_MISMATCH"
    similarity, reasons = _similarity(target, hit)
    if similarity < 35.0:
        return None, "SIMILARITY_BELOW_THRESHOLD"
    nok = unit_amount * fx_rates_to_nok[currency] if currency in fx_rates_to_nok else None
    actual_lane = "WHOLESALE" if _tokens(text) & _WHOLESALE_TERMS else lane
    return {
        "comparable_id": "comparable:" + sha256(url.encode()).hexdigest()[:24],
        "lane": actual_lane,
        "title": _compact(hit.title)[:500],
        "source_url": url,
        "source_domain": urlsplit(url).hostname,
        "description": _compact(hit.description)[:1000],
        "provider": _compact(hit.provider),
        "visible_price": amount,
        "currency": currency,
        "comparison_basis": basis,
        "visible_quantity": visible_quantity,
        "unit_price": round(unit_amount, 4),
        "unit_price_nok": round(nok, 4) if nok is not None else None,
        "fx_conversion_status": "CONVERTED_TO_NOK" if nok is not None else "FX_RATE_MISSING",
        "basis_note": basis_note,
        "similarity_score": similarity,
        "similarity_reasons": reasons,
        "asking_price_not_completed_sale": True,
        "source_evidence": {
            "title": _compact(hit.title),
            "description": _compact(hit.description),
            "source_url": url,
        },
    }, None


def _percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("values required")
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(len(ordered) - 1, lower + 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _range(comparables: Sequence[Mapping[str, Any]], target_currency: str | None) -> dict[str, Any] | None:
    nok_values = [float(value["unit_price_nok"]) for value in comparables if _number(value.get("unit_price_nok")) is not None]
    currency = "NOK"
    values = nok_values
    if not values and target_currency:
        values = [
            float(value["unit_price"])
            for value in comparables
            if value.get("currency") == target_currency and _number(value.get("unit_price")) is not None
        ]
        currency = target_currency
    if not values:
        return None
    return {
        "count": len(values),
        "currency": currency,
        "basis": comparables[0].get("comparison_basis") if comparables else None,
        "low": round(_percentile(values, 0.25), 2),
        "median": round(float(median(values)), 2),
        "high": round(_percentile(values, 0.75), 2),
        "range_method": "P25_MEDIAN_P75_OF_PUBLIC_ASKING_PRICES",
    }


def _classification(target_price: Mapping[str, Any], wholesale: Mapping[str, Any] | None, retail: Mapping[str, Any] | None) -> tuple[str, str | None, float | None]:
    reference = wholesale if wholesale and int(wholesale.get("count") or 0) >= 3 else retail if retail and int(retail.get("count") or 0) >= 3 else None
    if reference is None:
        return "INSUFFICIENT_COMPARABLES", None, None
    target_amount = target_price.get("amount_nok") if reference.get("currency") == "NOK" else target_price.get("amount") if reference.get("currency") == target_price.get("currency") else None
    if _number(target_amount) is None:
        return "MARKET_RANGE_AVAILABLE_TARGET_PRICE_MISSING", "WHOLESALE" if reference is wholesale else "RETAIL", None
    reference_median = float(reference["median"])
    ratio = float(target_amount) / reference_median if reference_median > 0 else None
    if ratio is None:
        return "INSUFFICIENT_COMPARABLES", None, None
    if ratio <= 0.60:
        classification = "CLEARLY_BELOW_MARKET"
    elif ratio <= 0.85:
        classification = "BELOW_MARKET_REQUIRES_VERIFICATION"
    elif ratio <= 1.15:
        classification = "NEAR_MARKET"
    else:
        classification = "ABOVE_MARKET"
    return classification, "WHOLESALE" if reference is wholesale else "RETAIL", round(ratio, 4)


def _fx_rates(environment: Mapping[str, str], supplied: Mapping[str, float] | None) -> dict[str, float]:
    rates = {"NOK": 1.0}
    if supplied:
        rates.update({str(key).upper(): float(value) for key, value in supplied.items() if float(value) > 0})
    for currency in ("SEK", "DKK", "EUR", "GBP", "USD", "PLN"):
        raw = _compact(environment.get(f"MARKET_COMPARABLES_FX_{currency}_NOK"))
        if not raw:
            continue
        try:
            rate = float(raw)
        except ValueError:
            continue
        if rate > 0:
            rates[currency] = rate
    return rates


def build_market_comparables_benchmark(
    *,
    brief: Mapping[str, Any],
    cases_report: Mapping[str, Any],
    items_report: Mapping[str, Any],
    environment: Mapping[str, str],
    provider_factory: ProviderFactory = _default_provider_factory,
    fx_rates_to_nok: Mapping[str, float] | None = None,
    generated_at: datetime | None = None,
    max_targets: int = MAX_TARGETS,
    results_per_query: int = RESULTS_PER_QUERY,
) -> dict[str, Any]:
    if not 1 <= max_targets <= MAX_TARGETS:
        raise ValueError("max_targets exceeds bounded limit")
    if not 1 <= results_per_query <= RESULTS_PER_QUERY:
        raise ValueError("results_per_query exceeds bounded limit")
    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    targets = select_benchmark_targets(brief, cases_report, items_report, max_targets=max_targets)
    rates = _fx_rates(environment, fx_rates_to_nok)
    api_key = _compact(environment.get("BRAVE_SEARCH_API_KEY")) or _compact(environment.get("BRAVE_API_KEY"))
    base: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "feed_family": FEED_FAMILY,
        "purpose": "PUBLIC_ASKING_PRICE_BENCHMARK_BEFORE_SHIPPING_ANALYSIS",
        "target_limit": MAX_TARGETS,
        "queries_per_target": QUERIES_PER_TARGET,
        "results_per_query": RESULTS_PER_QUERY,
        "maximum_comparables_per_target": MAX_COMPARABLES_PER_TARGET,
        "target_count": len(targets),
        "requests_made": 0,
        "hits_received": 0,
        "accepted_comparable_count": 0,
        "target_benchmarks": [],
        "errors": [],
        "fx_rates_to_nok_used": rates,
        "shipping_included": False,
        "auction_fees_included": False,
        "tax_included": False,
        "asking_prices_not_completed_sales": True,
        "decision_owner": DECISION_OWNER,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    if not targets:
        return {**base, "status": "VALID_ZERO", "status_counts": {"VALID_ZERO": 1}, "block_reason": "NO_ACTIONABLE_TARGETS"}
    if not api_key:
        return {**base, "status": "BLOCKED_CONFIGURATION", "status_counts": {"BLOCKED_CONFIGURATION": 1}, "block_reason": "BRAVE_SEARCH_API_KEY_MISSING"}

    for target in targets:
        target_basis = _target_basis(target)
        target_price = _target_price(target, rates)
        queries = build_comparable_queries(target)
        accepted: list[dict[str, Any]] = []
        rejected: Counter[str] = Counter()
        query_records: list[dict[str, Any]] = []
        try:
            provider = provider_factory(_compact(target.get("source_country")).upper() or "NO", api_key, DEFAULT_FRESHNESS)
        except Exception as exc:
            base["errors"].append(f"provider:{target.get('intelligence_id')}:{type(exc).__name__}:{_compact(exc)[:250]}")
            continue
        for query_record in queries:
            lane = query_record["lane"]
            query = query_record["query"]
            try:
                hits = list(provider.search(query, count=results_per_query))
                base["requests_made"] += 1
                base["hits_received"] += len(hits)
            except Exception as exc:
                base["errors"].append(f"search:{target.get('intelligence_id')}:{lane}:{type(exc).__name__}:{_compact(exc)[:250]}")
                query_records.append({"lane": lane, "query": query, "status": "FAILED", "hit_count": 0})
                continue
            query_records.append({"lane": lane, "query": query, "status": "SUCCESS", "hit_count": len(hits)})
            for hit in hits:
                comparable, reason = comparable_from_hit(
                    target=target,
                    hit=hit,
                    lane=lane,
                    fx_rates_to_nok=rates,
                )
                if comparable:
                    accepted.append(comparable)
                elif reason:
                    rejected[reason] += 1
        deduped = {
            _compact(value.get("source_url")): value
            for value in sorted(accepted, key=lambda value: (-float(value.get("similarity_score") or 0), _compact(value.get("source_url"))))
            if _compact(value.get("source_url"))
        }
        comparables = list(deduped.values())[:MAX_COMPARABLES_PER_TARGET]
        wholesale = [value for value in comparables if value.get("lane") == "WHOLESALE"]
        retail = [value for value in comparables if value.get("lane") == "RETAIL"]
        wholesale_range = _range(wholesale, target_price.get("currency"))
        retail_range = _range(retail, target_price.get("currency"))
        classification, reference_lane, ratio = _classification(target_price, wholesale_range, retail_range)
        base["accepted_comparable_count"] += len(comparables)
        base["target_benchmarks"].append(
            {
                "rank": target.get("rank"),
                "case_id": target.get("case_id"),
                "intelligence_id": target.get("intelligence_id"),
                "title": target.get("title"),
                "record_kind": target.get("record_kind"),
                "source_country": target.get("source_country"),
                "source_url": target.get("source_url"),
                "brands": target.get("brands"),
                "comparison_basis": target_basis,
                "target_price": target_price,
                "queries": query_records,
                "comparable_count": len(comparables),
                "comparables": comparables,
                "rejection_counts": dict(sorted(rejected.items())),
                "wholesale_range": wholesale_range,
                "retail_range": retail_range,
                "benchmark_classification": classification,
                "reference_lane": reference_lane,
                "target_to_reference_median_ratio": ratio,
                "confidence": "HIGH" if len(comparables) >= 7 else "MEDIUM" if len(comparables) >= 3 else "LOW",
                "recommended_next_action": (
                    "CHECK_SHIPPING_FEES_CONDITION_AND_FINAL_PRICE"
                    if classification in {"CLEARLY_BELOW_MARKET", "BELOW_MARKET_REQUIRES_VERIFICATION"}
                    else "VERIFY_MORE_COMPARABLES_BEFORE_COST_ANALYSIS"
                    if classification in {"INSUFFICIENT_COMPARABLES", "MARKET_RANGE_AVAILABLE_TARGET_PRICE_MISSING"}
                    else "REVIEW_MARKET_POSITION_BEFORE_SHIPPING_ANALYSIS"
                ),
                "decision_owner": DECISION_OWNER,
            }
        )

    if base["accepted_comparable_count"] > 0 and base["errors"]:
        status = "PARTIAL_SUCCESS"
    elif base["accepted_comparable_count"] > 0:
        status = "SUCCESS"
    elif base["errors"]:
        status = "BLOCKED_RETRIEVAL"
    else:
        status = "VALID_ZERO"
    return {**base, "status": status, "status_counts": {status: 1}, "block_reason": None}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_market_comparables_benchmark(
    output_dir: Path,
    *,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory = _default_provider_factory,
    fx_rates_to_nok: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    brief_path = output_dir / "unified-daily-decision-brief.json"
    cases_path = output_dir / "unified-market-cases.json"
    items_path = output_dir / "unified-intelligence-items.json"
    if not (brief_path.exists() and cases_path.exists() and items_path.exists()):
        report = {
            "schema_version": SCHEMA_VERSION,
            "feed_family": FEED_FAMILY,
            "status": "BLOCKED_INPUT",
            "status_counts": {"BLOCKED_INPUT": 1},
            "block_reason": "UNIFIED_RIVER_ARTIFACTS_MISSING",
            "target_count": 0,
            "target_benchmarks": [],
            "requests_made": 0,
            "decision_owner": DECISION_OWNER,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }
        _write_json(output_dir / OUTPUT_FILENAME, report)
        return report
    report = build_market_comparables_benchmark(
        brief=_load_json(brief_path),
        cases_report=_load_json(cases_path),
        items_report=_load_json(items_path),
        environment=environment if environment is not None else os.environ,
        provider_factory=provider_factory,
        fx_rates_to_nok=fx_rates_to_nok,
    )
    _write_json(output_dir / OUTPUT_FILENAME, report)

    brief = _load_json(brief_path)
    brief["market_comparables_benchmark"] = {
        "schema_version": report.get("schema_version"),
        "status": report.get("status"),
        "target_count": report.get("target_count"),
        "requests_made": report.get("requests_made"),
        "accepted_comparable_count": report.get("accepted_comparable_count"),
        "target_benchmarks": report.get("target_benchmarks"),
        "shipping_included": False,
        "decision_owner": DECISION_OWNER,
    }
    _write_json(brief_path, brief)

    domain_path = output_dir / "domain-market-intelligence-brief.json"
    if domain_path.exists():
        domain = _load_json(domain_path)
        river_summary = domain.get("unified_market_intelligence_river")
        if not isinstance(river_summary, dict):
            river_summary = {}
            domain["unified_market_intelligence_river"] = river_summary
        river_summary["market_comparables_benchmark"] = {
            "status": report.get("status"),
            "target_count": report.get("target_count"),
            "accepted_comparable_count": report.get("accepted_comparable_count"),
            "output_file": OUTPUT_FILENAME,
        }
        _write_json(domain_path, domain)

    text_path = output_dir / "domain-market-intelligence-brief.txt"
    if text_path.exists():
        with text_path.open("a", encoding="utf-8") as handle:
            handle.write("\nMARKET COMPARABLES BENCHMARK\n")
            handle.write(f"status: {report.get('status')}\n")
            handle.write(f"targets: {report.get('target_count', 0)}\n")
            handle.write(f"comparables: {report.get('accepted_comparable_count', 0)}\n")
            for target in report.get("target_benchmarks") or []:
                handle.write(
                    f"- {target.get('title')} | {target.get('benchmark_classification')} | "
                    f"comparables={target.get('comparable_count')} | "
                    f"shipping_included=false\n"
                )
            handle.write("decision_owner: HUMAN_OPERATOR\n")
            handle.write("automatic_purchase: false\n")
    return report
