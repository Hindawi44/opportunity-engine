"""Bounded official-domain watch for bridal and premium deadstock fabrics.

This is a procurement-intelligence lane for the operator's tailoring shop. It is
not a clothing-liquidation opportunity collector. Search results remain advisory
and never trigger contact, ordering, reservation, payment, or opportunity
promotion.
"""
from __future__ import annotations

from dataclasses import dataclass
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


SCHEMA_VERSION = "fabric-procurement-watch-1.0"
FEED_FAMILY = "FABRIC_DEADSTOCK_PROCUREMENT_FEED_V1"
DEFAULT_RESULTS_PER_SOURCE = 8
MAX_RESULTS_PER_SOURCE = 10
MAX_ACCEPTED_PER_SOURCE = 5
DEFAULT_FRESHNESS = "pm"


@dataclass(frozen=True, slots=True)
class FabricSource:
    source_id: str
    name: str
    domain: str
    country: str
    query: str
    source_kind: str


SOURCES: tuple[FabricSource, ...] = (
    FabricSource(
        source_id="eva-resource",
        name="EVA re-source",
        domain="evaresource.com",
        country="IT",
        query=(
            'site:evaresource.com (deadstock OR "deadstock deals" OR sale) '
            '(silk OR satin OR duchesse OR mikado OR organza OR chiffon OR lace OR tulle) '
            '(ivory OR white OR bridal OR wedding)'
        ),
        source_kind="ITALIAN_DEADSTOCK",
    ),
    FabricSource(
        source_id="fabric-house",
        name="Fabric House",
        domain="fabrichouse.com",
        country="IT",
        query=(
            'site:fabrichouse.com (deadstock OR sale OR clearance OR "new arrivals") '
            '(silk OR satin OR duchesse OR mikado OR organza OR chiffon OR lace OR tulle) '
            '(ivory OR white OR bridal OR wedding)'
        ),
        source_kind="ITALIAN_DEADSTOCK",
    ),
    FabricSource(
        source_id="bridal-fabrics",
        name="Bridal Fabrics",
        domain="bridalfabrics.com",
        country="GB",
        query=(
            'site:bridalfabrics.com (lace OR tulle OR satin OR mikado OR organza OR chiffon) '
            '(ivory OR white OR bridal OR wedding) (sale OR sample OR fabric OR trim)'
        ),
        source_kind="SPECIALIST_BRIDAL_SUPPLIER",
    ),
)

ProviderFactory = Callable[[str, str, str | None], SearchProvider]

_FABRIC_TERMS = (
    "silk",
    "satin",
    "mikado",
    "duchesse",
    "organza",
    "chiffon",
    "tulle",
    "lace",
    "crepe",
    "crêpe",
    "jacquard",
    "fabric",
    "fabrics",
    "textile",
)
_BRIDAL_TERMS = (
    "bridal",
    "wedding",
    "ivory",
    "white",
    "champagne",
    "cream",
    "bride",
)
_VALUE_TERMS = (
    "deadstock",
    "sale",
    "clearance",
    "deal",
    "discount",
    "stock",
    "in stock",
    "new arrival",
    "sample",
    "last metres",
    "last meters",
    "final quantity",
)
_PREMIUM_TERMS = (
    "silk",
    "mikado",
    "duchesse",
    "organza",
    "lace",
    "tulle",
    "chiffon",
)
_PRICE_RE = re.compile(
    r"(?P<symbol>€|£|\$)\s?(?P<amount>\d{1,5}(?:[.,]\d{1,2})?)"
    r"|(?P<amount2>\d{1,5}(?:[.,]\d{1,2})?)\s?(?P<code>EUR|GBP|USD)",
    re.IGNORECASE,
)


def _safety_payload() -> dict[str, bool]:
    return {
        "promotion_to_opportunity_allowed": False,
        "analysis_eligible": False,
        "top5_eligible": False,
        "automatic_contact": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _matched_terms(text: str, terms: Sequence[str]) -> list[str]:
    folded = text.casefold()
    return sorted({term for term in terms if term.casefold() in folded})


def _official_domain(url: str, domain: str) -> bool:
    host = (urlsplit(url).hostname or "").casefold().rstrip(".")
    expected = domain.casefold().rstrip(".")
    return host == expected or host.endswith(f".{expected}")


def _extract_price(text: str) -> tuple[str | None, float | None, str | None]:
    match = _PRICE_RE.search(text)
    if not match:
        return None, None, None
    raw_amount = match.group("amount") or match.group("amount2")
    if not raw_amount:
        return None, None, None
    try:
        amount = float(raw_amount.replace(",", "."))
    except ValueError:
        return None, None, None
    symbol = match.group("symbol")
    code = (match.group("code") or "").upper()
    currency = {"€": "EUR", "£": "GBP", "$": "USD"}.get(symbol or "", code or None)
    return match.group(0), amount, currency


def procurement_candidate_from_hit(
    hit: SearchHit,
    *,
    source: FabricSource,
    observed_at: datetime,
) -> dict[str, Any] | None:
    """Normalize one official supplier result into an advisory procurement row."""
    if not isinstance(hit, SearchHit):
        return None
    title = _compact(hit.title)
    description = _compact(hit.description)
    raw_url = _compact(hit.url)
    if not title or not raw_url:
        return None
    try:
        canonical_url = _canonical_url(raw_url)
    except ValueError:
        return None
    if not _official_domain(canonical_url, source.domain):
        return None

    combined = f"{title} {description}".strip()
    fabric_terms = _matched_terms(combined, _FABRIC_TERMS)
    bridal_terms = _matched_terms(combined, _BRIDAL_TERMS)
    value_terms = _matched_terms(combined, _VALUE_TERMS)
    if not fabric_terms:
        return None
    if source.source_kind == "SPECIALIST_BRIDAL_SUPPLIER":
        if not bridal_terms:
            return None
    elif not value_terms:
        return None

    price_text, price, currency = _extract_price(combined)
    score = 40
    if _matched_terms(combined, _PREMIUM_TERMS):
        score += 20
    if bridal_terms:
        score += 15
    if value_terms:
        score += 15
    if price is not None:
        score += 10
    score = min(100, score)

    candidate_id = (
        f"fabric-watch:{source.source_id}:"
        f"{sha256(canonical_url.encode('utf-8')).hexdigest()[:24]}"
    )
    return {
        "candidate_id": candidate_id,
        "source_id": source.source_id,
        "source_name": source.name,
        "source_country": source.country,
        "source_kind": source.source_kind,
        "title": title[:1000],
        "description": (description or title)[:1000],
        "source_url": canonical_url,
        "observed_at": _iso_utc(observed_at),
        "fabric_terms": fabric_terms,
        "bridal_terms": bridal_terms,
        "value_terms": value_terms,
        "price_text": price_text,
        "price": price,
        "currency": currency,
        "procurement_relevance_score": score,
        "recommended_operator_action": "REVIEW_SAMPLE_PRICE_AND_SHIPPING",
        "verification_status": "UNVERIFIED_SEARCH_RESULT",
        "not_a_liquidation_opportunity": True,
        **_safety_payload(),
    }


def collect_fabric_procurement_watch(
    *,
    observed_at: datetime | None = None,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory = _default_provider_factory,
    results_per_source: int = DEFAULT_RESULTS_PER_SOURCE,
    freshness: str | None = DEFAULT_FRESHNESS,
) -> dict[str, Any]:
    """Run one official-domain Brave query for each approved fabric supplier."""
    if not 1 <= results_per_source <= MAX_RESULTS_PER_SOURCE:
        raise ValueError(
            f"results_per_source must be between 1 and {MAX_RESULTS_PER_SOURCE}"
        )

    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    env = environment if environment is not None else os.environ
    api_key = _compact(env.get("BRAVE_SEARCH_API_KEY")) or _compact(
        env.get("BRAVE_API_KEY")
    )

    reports: list[dict[str, Any]] = []
    requests_made = 0
    all_candidates: dict[str, dict[str, Any]] = {}

    for source in SOURCES:
        report: dict[str, Any] = {
            "source_id": source.source_id,
            "source_name": source.name,
            "official_domain": source.domain,
            "source_country": source.country,
            "source_kind": source.source_kind,
            "query": source.query,
            "query_budget": 1,
            "queries_attempted": 0,
            "queries_succeeded": 0,
            "accepted_candidate_count": 0,
            "rejected_result_count": 0,
            "duplicate_result_count": 0,
            "candidates": [],
            "errors": [],
            **_safety_payload(),
        }
        if not api_key:
            report["status"] = "BLOCKED_CONFIGURATION"
            report["block_reason"] = "BRAVE_SEARCH_API_KEY_MISSING"
            reports.append(report)
            continue

        try:
            provider = provider_factory(source.country, api_key, freshness)
        except Exception as exc:
            report["status"] = "BLOCKED_RETRIEVAL"
            report["block_reason"] = "PROVIDER_INITIALIZATION_FAILED"
            report["errors"] = [f"{type(exc).__name__}: {_compact(exc)[:300]}"]
            reports.append(report)
            continue

        report["queries_attempted"] = 1
        requests_made += 1
        try:
            hits = provider.search(source.query, count=results_per_source)
            report["queries_succeeded"] = 1
        except Exception as exc:
            report["status"] = "BLOCKED_RETRIEVAL"
            report["block_reason"] = "SEARCH_REQUEST_FAILED"
            report["errors"] = [f"{type(exc).__name__}: {_compact(exc)[:300]}"]
            reports.append(report)
            continue

        accepted: dict[str, dict[str, Any]] = {}
        seen_urls: set[str] = set()
        rejected = 0
        duplicates = 0
        for hit in hits:
            if not isinstance(hit, SearchHit):
                rejected += 1
                continue
            try:
                canonical_url = _canonical_url(_compact(hit.url))
            except ValueError:
                rejected += 1
                continue
            if canonical_url in seen_urls:
                duplicates += 1
                continue
            seen_urls.add(canonical_url)
            candidate = procurement_candidate_from_hit(
                hit,
                source=source,
                observed_at=now,
            )
            if candidate is None:
                rejected += 1
                continue
            accepted[candidate["candidate_id"]] = candidate

        selected = sorted(
            accepted.values(),
            key=lambda item: (
                -int(item["procurement_relevance_score"]),
                str(item["source_url"]),
            ),
        )[:MAX_ACCEPTED_PER_SOURCE]
        for candidate in selected:
            all_candidates[candidate["candidate_id"]] = candidate
        report["accepted_candidate_count"] = len(selected)
        report["rejected_result_count"] = rejected
        report["duplicate_result_count"] = duplicates
        report["candidates"] = selected
        report["status"] = "SUCCESS" if selected else "VALID_ZERO"
        report["block_reason"] = None
        reports.append(report)

    candidates = sorted(
        all_candidates.values(),
        key=lambda item: (
            -int(item["procurement_relevance_score"]),
            str(item["source_name"]),
            str(item["source_url"]),
        ),
    )
    status_counts: dict[str, int] = {}
    for report in reports:
        status = _compact(report.get("status")).upper() or "UNKNOWN"
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso_utc(now),
        "feed_family": FEED_FAMILY,
        "purpose": "TAILORING_SHOP_FABRIC_PROCUREMENT_INTELLIGENCE",
        "search_language": "en",
        "approved_official_domains": [source.domain for source in SOURCES],
        "source_count": len(SOURCES),
        "query_budget_total": len(SOURCES),
        "requests_made": requests_made,
        "results_per_source": results_per_source,
        "freshness": freshness,
        "status_counts": status_counts,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "sources": reports,
        "operator_rule": "COMPARE_PRICE_SAMPLE_COMPOSITION_AND_SHIPPING_BEFORE_ORDER",
        "seller_or_source_verification_required": True,
        "not_part_of_opportunity_top5": True,
        **_safety_payload(),
    }
