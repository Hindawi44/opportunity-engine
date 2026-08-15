"""Targeted Sweden/Germany clothing-liquidation radar with bounded adaptive search.

Primary searches remain source-specific and deterministic. When a primary source
produces no accepted signal, a bounded adaptive layer tries alternative local
vocabulary on the same source. A second tier follows only the strongest scent.
All results remain signals only and require source-page verification.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import re
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from opportunity_engine.discovery.brave_market_signal_radar import (
    MarketRadarQuery,
    _compact,
    _default_provider_factory,
    _iso_utc,
    _target_spec,
    _write_merged_market_signal_report,
    market_signal_from_brave_hit,
)
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider

SCHEMA_VERSION = "se-de-source-coverage-gap-1.6"
FEED_FAMILY = "SE_DE_SOURCE_COVERAGE_GAP_V1"
COVERAGE_HEALTH_VERSION = "SE_DE_COVERAGE_HEALTH_V1"
SOURCE_YIELD_DIAGNOSTICS_VERSION = "SE_DE_SOURCE_YIELD_DIAGNOSTICS_V1"
ADAPTIVE_SEARCH_EXPANSION_VERSION = "ADAPTIVE_SEARCH_EXPANSION_ENGINE_V1"
SUPPORTED_MARKETS = ("SE", "DE")
DEFAULT_RESULTS_PER_QUERY = 8
MAX_RESULTS_PER_QUERY = 10
DEFAULT_FRESHNESS = "pm"
DEFAULT_ADAPTIVE_MAX_REQUESTS = 12
MAX_ADAPTIVE_MAX_REQUESTS = 30

ProviderFactory = Callable[[str, str, str | None], SearchProvider]


@dataclass(frozen=True, slots=True)
class CoverageSourceQuery:
    query_id: str
    source_name: str
    source_domain: str
    query: str
    source_role: str = "DIRECT_SALE_OR_AUCTION_SOURCE"


@dataclass(frozen=True, slots=True)
class AdaptiveExpansionQuery:
    query_id: str
    parent_query_id: str
    source_name: str
    source_domain: str
    source_role: str
    query: str
    tier: int


SOURCE_QUERIES: dict[str, tuple[CoverageSourceQuery, ...]] = {
    "SE": (
        CoverageSourceQuery("se-budi-bankruptcy-clothing", "Budi Auktioner", "budi.se", 'site:budi.se (konkursauktion OR konkurslager OR varulager OR utförsäljning) (kläder OR skor OR textil OR mode)'),
        CoverageSourceQuery("se-kronofogden-varuparti-clothing", "Kronofogden Webauktion", "auktion.kronofogden.se", 'site:auktion.kronofogden.se ("Varuparti" OR "Konkurslager" OR kläder OR skor) (auktion OR försäljning)'),
        CoverageSourceQuery("se-psauction-bankruptcy-clothing-stock", "PS Auction", "psauction.se", 'site:psauction.se (konkurs OR konkursauktion OR varulager OR "parti med") (kläder OR skor OR mode OR textil)'),
        CoverageSourceQuery("se-klaravik-bankruptcy-clothing-stock", "Klaravik", "klaravik.se", 'site:klaravik.se (konkursbo OR konkurs OR varulager OR konkursparti) (kläder OR märkeskläder OR skor OR klädbutik)'),
        CoverageSourceQuery("se-allabolag-clothing-insolvency", "Allabolag", "allabolag.se", 'site:allabolag.se/foretag ("Konkurs inledd") (kläder OR konfektion OR skodon OR mode OR textilier)', "EARLY_INSOLVENCY_SIGNAL_SOURCE"),
    ),
    "DE": (
        CoverageSourceQuery("de-htkg-insolvency-fashion", "HTKG Online-Versteigerungen", "online-versteigerungen.ht-kg.de", 'site:online-versteigerungen.ht-kg.de (Insolvenzversteigerung OR Warenbestand) (Mode OR Bekleidung OR Textil OR Kleidung)'),
        CoverageSourceQuery("de-sen-sen-textile-liquidation", "Sen & Sen", "sen-sen.de", 'site:sen-sen.de (Liquidationsverkauf OR Insolvenz OR Warenbestand) (Textil OR Bekleidung OR Arbeitskleidung OR Mode)'),
        CoverageSourceQuery("de-restlos-insolvency-clothing-stock", "RESTLOS", "restlos.com", 'site:restlos.com (Insolvenzauktion OR Insolvenzversteigerung OR Warenbestand) (Bekleidung OR Mode OR Textil OR Sportbekleidung)'),
        CoverageSourceQuery("de-versteigerungskalender-fashion-insolvency", "Versteigerungskalender", "versteigerungskalender.de", 'site:versteigerungskalender.de/insolvenzkalender (Insolvenzeröffnung OR Insolvenz) (Textilhandel OR Bekleidung OR Mode OR Schuhe)', "EARLY_INSOLVENCY_SIGNAL_SOURCE"),
    ),
}


def _exp(parent: CoverageSourceQuery, suffix: str, query: str, tier: int) -> AdaptiveExpansionQuery:
    return AdaptiveExpansionQuery(
        query_id=f"{parent.query_id}-{suffix}",
        parent_query_id=parent.query_id,
        source_name=parent.source_name,
        source_domain=parent.source_domain,
        source_role=parent.source_role,
        query=query,
        tier=tier,
    )


# Two deterministic alternatives per source. Tier 1 broadens vocabulary; Tier 2
# is reserved for the strongest scent and uses a different sale/lifecycle angle.
EXPANSION_FAMILIES: dict[str, tuple[AdaptiveExpansionQuery, AdaptiveExpansionQuery]] = {}
for _market, _items in SOURCE_QUERIES.items():
    for _item in _items:
        if _item.query_id == "se-budi-bankruptcy-clothing":
            EXPANSION_FAMILIES[_item.query_id] = (
                _exp(_item, "alt-stock", 'site:budi.se (lagerparti OR butikslager OR konkursbo OR avveckling) (kläder OR skor OR modebutik OR textil)', 1),
                _exp(_item, "alt-sale", 'site:budi.se (utförsäljning OR lagerrensning OR butikstömning) (kläder OR skor OR accessoarer OR konfektion)', 2),
            )
        elif _item.query_id == "se-kronofogden-varuparti-clothing":
            EXPANSION_FAMILIES[_item.query_id] = (
                _exp(_item, "alt-stock", 'site:auktion.kronofogden.se (varulager OR lagerparti OR butikslager) (kläder OR skor OR textil)', 1),
                _exp(_item, "alt-sale", 'site:auktion.kronofogden.se (försäljning OR auktion) (klädbutik OR modebutik OR konfektion OR skodon)', 2),
            )
        elif _item.query_id == "se-psauction-bankruptcy-clothing-stock":
            EXPANSION_FAMILIES[_item.query_id] = (
                _exp(_item, "alt-stock", 'site:psauction.se (lagerparti OR butikslager OR konkursbo OR avveckling) (kläder OR skor OR textil OR mode)', 1),
                _exp(_item, "alt-sale", 'site:psauction.se (utförsäljning OR konkursauktion OR lagerrensning) (klädbutik OR modebutik OR accessoarer)', 2),
            )
        elif _item.query_id == "se-klaravik-bankruptcy-clothing-stock":
            EXPANSION_FAMILIES[_item.query_id] = (
                _exp(_item, "alt-stock", 'site:klaravik.se (lagerparti OR butikslager OR konkursbo OR avveckling) (kläder OR skor OR textil)', 1),
                _exp(_item, "alt-sale", 'site:klaravik.se (auktion OR utförsäljning) (klädbutik OR modebutik OR märkeskläder OR skodon)', 2),
            )
        elif _item.query_id == "se-allabolag-clothing-insolvency":
            EXPANSION_FAMILIES[_item.query_id] = (
                _exp(_item, "alt-sector", 'site:allabolag.se/foretag (konkurs OR likvidation) ("detaljhandel med kläder" OR "partihandel med kläder" OR konfektion OR skodon)', 1),
                _exp(_item, "alt-company", 'site:allabolag.se/foretag (konkurs OR likvidation) (klädbutik OR modeföretag OR textilhandel OR skoaffär)', 2),
            )
        elif _item.query_id == "de-htkg-insolvency-fashion":
            EXPANSION_FAMILIES[_item.query_id] = (
                _exp(_item, "alt-stock", 'site:online-versteigerungen.ht-kg.de (Lagerauflösung OR Geschäftsauflösung OR Restposten OR Warenlager) (Bekleidung OR Mode OR Textil OR Schuhe)', 1),
                _exp(_item, "alt-sale", 'site:online-versteigerungen.ht-kg.de (Räumungsverkauf OR Versteigerung OR Insolvenz) (Modehaus OR Bekleidungsgeschäft OR Schuhhandel)', 2),
            )
        elif _item.query_id == "de-sen-sen-textile-liquidation":
            EXPANSION_FAMILIES[_item.query_id] = (
                _exp(_item, "alt-stock", 'site:sen-sen.de (Lagerauflösung OR Geschäftsauflösung OR Restposten OR Warenlager) (Bekleidung OR Mode OR Textil OR Schuhe)', 1),
                _exp(_item, "alt-sale", 'site:sen-sen.de (Liquidation OR Räumungsverkauf OR Versteigerung) (Modehaus OR Bekleidungsgeschäft OR Textilhandel)', 2),
            )
        elif _item.query_id == "de-restlos-insolvency-clothing-stock":
            EXPANSION_FAMILIES[_item.query_id] = (
                _exp(_item, "alt-stock", 'site:restlos.com (Lagerauflösung OR Geschäftsauflösung OR Restposten OR Warenlager) (Bekleidung OR Mode OR Textil OR Schuhe)', 1),
                _exp(_item, "alt-sale", 'site:restlos.com (Räumungsverkauf OR Insolvenzauktion OR Versteigerung) (Modehaus OR Bekleidungsgeschäft OR Sportbekleidung)', 2),
            )
        elif _item.query_id == "de-versteigerungskalender-fashion-insolvency":
            EXPANSION_FAMILIES[_item.query_id] = (
                _exp(_item, "alt-sector", 'site:versteigerungskalender.de/insolvenzkalender (Insolvenz OR Liquidation) ("Einzelhandel mit Bekleidung" OR Textilhandel OR Modehaus OR Schuhhandel)', 1),
                _exp(_item, "alt-company", 'site:versteigerungskalender.de/insolvenzkalender (Insolvenzverfahren OR Insolvenzeröffnung) (Bekleidungsunternehmen OR Modeunternehmen OR Textilunternehmen)', 2),
            )

_COMMON_CLOTHING_TERMS = ("clothing", "fashion", "apparel", "garment", "footwear")
_MARKET_CLOTHING_TERMS: dict[str, tuple[str, ...]] = {
    "SE": ("kläder", "klader", "skor", "textil", "mode", "märkeskläder", "markesklader", "klädbutik", "kladbutik", "modebutik", "konfektion", "skodon", "textilier", "plagg", "accessoarer"),
    "DE": ("bekleidung", "kleidung", "textil", "mode", "modehaus", "schuhe", "schuhhandel", "sportbekleidung", "arbeitskleidung", "konfektion", "bekleidungsgeschäft", "bekleidungsunternehmen", "modeunternehmen", "textilunternehmen"),
}
_MARKET_EVENT_TERMS: dict[str, tuple[str, ...]] = {
    "SE": ("konkurs", "auktion", "varulager", "lagerparti", "butikslager", "utförsäljning", "avveckling", "likvidation", "försäljning"),
    "DE": ("insolvenz", "auktion", "versteigerung", "warenbestand", "warenlager", "lagerauflösung", "geschäftsauflösung", "räumungsverkauf", "restposten", "liquidation"),
}
_OFF_TOPIC_TITLE_TERMS: dict[str, tuple[str, ...]] = {
    "SE": ("restaurang", "restaurangutrustning", "storkök", "kök", "bageri", "verktyg", "fordon", "maskiner"),
    "DE": ("restaurant", "gastronomie", "küchenausstattung", "maschinen", "fahrzeuge", "werkzeuge", "baugeräte"),
}


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


def _approved_domain(url: str, domain: str) -> bool:
    host = (urlsplit(url).hostname or "").casefold().rstrip(".")
    expected = domain.casefold().rstrip(".")
    return host == expected or host.endswith(f".{expected}")


def _term_present(text: str, term: str) -> bool:
    text = text.casefold()
    term = term.casefold()
    if " " in term or "-" in term:
        return term in text
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None


def _matches_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(_term_present(text, term) for term in terms)


def _hit_text(hit: SearchHit) -> str:
    # URL/category slugs are intentionally excluded: Run #143 proved they can
    # leak generic category words into an otherwise irrelevant result.
    return " ".join((_compact(getattr(hit, "title", "")), _compact(getattr(hit, "description", "")))).casefold()


def _has_clothing_relevance(hit: SearchHit, market_code: str, source_role: str = "DIRECT_SALE_OR_AUCTION_SOURCE") -> bool:
    market = market_code.upper()
    title = _compact(getattr(hit, "title", "")).casefold()
    description = _compact(getattr(hit, "description", "")).casefold()
    clothing_terms = _COMMON_CLOTHING_TERMS + _MARKET_CLOTHING_TERMS.get(market, ())
    title_clothing = _matches_any(title, clothing_terms)
    body_clothing = _matches_any(description, clothing_terms)
    if source_role == "EARLY_INSOLVENCY_SIGNAL_SOURCE":
        return title_clothing or body_clothing
    if _matches_any(title, _OFF_TOPIC_TITLE_TERMS.get(market, ())) and not title_clothing:
        return False
    if title_clothing:
        return True
    return body_clothing and _matches_any(description, _MARKET_EVENT_TERMS.get(market, ()))


def _radar_query(item: CoverageSourceQuery | AdaptiveExpansionQuery) -> MarketRadarQuery:
    return MarketRadarQuery(query_id=item.query_id, query=item.query)


def _candidate_from_hit_with_reason(
    hit: SearchHit,
    *,
    market_code: str,
    source_query: CoverageSourceQuery | AdaptiveExpansionQuery,
    rank: int,
    observed_at: datetime,
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(hit, SearchHit):
        return None, "INVALID_HIT"
    if not _approved_domain(_compact(hit.url), source_query.source_domain):
        return None, "UNAPPROVED_DOMAIN"
    if not _has_clothing_relevance(hit, market_code, source_query.source_role):
        return None, "CLOTHING_RELEVANCE_MISSING"
    signal = market_signal_from_brave_hit(
        hit,
        market_code=market_code,
        query=_radar_query(source_query),
        rank=rank,
        observed_at=observed_at,
    )
    if signal is None:
        return None, "MARKET_SIGNAL_REJECTED"
    payload = signal.model_dump(mode="json")
    payload["source"] = "SE/DE source coverage gap radar"
    metadata = dict(payload.get("metadata") or {})
    metadata.update(
        {
            "coverage_gap_feed_family": FEED_FAMILY,
            "coverage_gap_source_name": source_query.source_name,
            "coverage_gap_source_domain": source_query.source_domain,
            "coverage_gap_source_role": source_query.source_role,
            "source_page_verification_required": True,
            "promotion_to_opportunity_allowed": False,
        }
    )
    if isinstance(source_query, AdaptiveExpansionQuery):
        metadata.update(
            {
                "adaptive_search_expansion_version": ADAPTIVE_SEARCH_EXPANSION_VERSION,
                "adaptive_parent_query_id": source_query.parent_query_id,
                "adaptive_query_id": source_query.query_id,
                "adaptive_expansion_tier": source_query.tier,
                "adaptive_signal_only": True,
            }
        )
    payload["metadata"] = metadata
    return payload, None


def _candidate_from_hit(hit: SearchHit, *, market_code: str, source_query: CoverageSourceQuery, rank: int, observed_at: datetime) -> dict[str, Any] | None:
    candidate, _ = _candidate_from_hit_with_reason(hit, market_code=market_code, source_query=source_query, rank=rank, observed_at=observed_at)
    return candidate


def _ratio(numerator: int, denominator: int) -> float:
    return 0.0 if denominator <= 0 else round(numerator / denominator, 3)


def _coverage_health(report: Mapping[str, Any]) -> dict[str, Any]:
    query_budget = int(report.get("query_budget") or 0)
    attempted = int(report.get("queries_attempted") or 0)
    succeeded = int(report.get("queries_succeeded") or 0)
    accepted = int(report.get("primary_accepted_signal_count", report.get("accepted_signal_count") or 0) or 0)
    rejected = int(report.get("primary_rejected_result_count", report.get("rejected_result_count") or 0) or 0)
    duplicates = int(report.get("primary_duplicate_result_count", report.get("duplicate_result_count") or 0) or 0)
    source_queries = [item for item in (report.get("source_queries") or []) if isinstance(item, Mapping)]
    diagnostics = [item for item in (report.get("query_diagnostics") or []) if isinstance(item, Mapping)]
    roles = sorted({str(item.get("source_role") or "UNKNOWN") for item in source_queries})
    direct = sum(1 for item in source_queries if item.get("source_role") == "DIRECT_SALE_OR_AUCTION_SOURCE")
    early = sum(1 for item in source_queries if item.get("source_role") == "EARLY_INSOLVENCY_SIGNAL_SOURCE")
    observed = accepted + rejected + duplicates
    productive = sum(1 for item in diagnostics if int(item.get("accepted_count") or 0) > 0)
    result_bearing = sum(1 for item in diagnostics if int(item.get("result_count") or 0) > 0)
    zero_results = sum(1 for item in diagnostics if item.get("search_status") == "SUCCESS" and int(item.get("result_count") or 0) == 0)
    relevance_rejections = sum(int((item.get("rejection_reasons") or {}).get("CLOTHING_RELEVANCE_MISSING") or 0) for item in diagnostics)
    retrieval_rate = _ratio(succeeded, query_budget)
    yield_rate = _ratio(accepted, succeeded)
    if attempted == 0 or succeeded == 0:
        diagnosis = "RETRIEVAL_BLOCKED"
    elif retrieval_rate < 0.8:
        diagnosis = "RETRIEVAL_GAP"
    elif accepted == 0 and observed == 0:
        diagnosis = "HEALTHY_ZERO_SIGNAL"
    elif accepted == 0:
        diagnosis = "RESULTS_SEEN_BUT_NONE_ACCEPTED"
    elif yield_rate < 0.25:
        diagnosis = "LOW_SIGNAL_YIELD"
    else:
        diagnosis = "SIGNAL_FLOWING"
    return {
        "market_code": report.get("source_country"),
        "query_budget": query_budget,
        "queries_attempted": attempted,
        "queries_succeeded": succeeded,
        "retrieval_rate": retrieval_rate,
        "accepted_signal_count": accepted,
        "rejected_result_count": rejected,
        "duplicate_result_count": duplicates,
        "observed_result_count": observed,
        "rejection_rate": _ratio(rejected, accepted + rejected),
        "signal_yield_per_successful_query": yield_rate,
        "source_count": len(source_queries),
        "direct_sale_or_auction_source_count": direct,
        "early_insolvency_source_count": early,
        "source_role_diversity": roles,
        "productive_source_count": productive,
        "productive_source_rate": _ratio(productive, query_budget),
        "result_bearing_source_count": result_bearing,
        "zero_result_source_count": zero_results,
        "clothing_relevance_rejection_count": relevance_rejections,
        "diagnosis": diagnosis,
    }


def _query_diagnostic(item: CoverageSourceQuery | AdaptiveExpansionQuery) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "query_id": item.query_id,
        "source_name": item.source_name,
        "source_domain": item.source_domain,
        "source_role": item.source_role,
        "search_status": "SUCCESS",
        "result_count": 0,
        "accepted_count": 0,
        "rejected_count": 0,
        "duplicate_count": 0,
        "rejection_reasons": {},
    }
    if isinstance(item, AdaptiveExpansionQuery):
        payload.update({"parent_query_id": item.parent_query_id, "tier": item.tier})
    return payload


def _run_query(
    provider: SearchProvider,
    item: CoverageSourceQuery | AdaptiveExpansionQuery,
    *,
    market_code: str,
    results_per_query: int,
    observed_at: datetime,
    seen_urls: set[str],
    accepted: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], str | None]:
    diagnostic = _query_diagnostic(item)
    try:
        hits = provider.search(item.query, count=results_per_query)
        diagnostic["result_count"] = len(hits)
    except Exception as exc:
        message = f"{item.query_id}: {type(exc).__name__}: {_compact(exc)[:300]}"
        diagnostic["search_status"] = "ERROR"
        diagnostic["error"] = message
        return diagnostic, message
    for rank, hit in enumerate(hits, start=1):
        raw_url = _compact(getattr(hit, "url", ""))
        if raw_url in seen_urls:
            diagnostic["duplicate_count"] = int(diagnostic["duplicate_count"]) + 1
            continue
        if raw_url:
            seen_urls.add(raw_url)
        candidate, reason = _candidate_from_hit_with_reason(hit, market_code=market_code, source_query=item, rank=rank, observed_at=observed_at)
        if candidate is None:
            diagnostic["rejected_count"] = int(diagnostic["rejected_count"]) + 1
            reasons = dict(diagnostic["rejection_reasons"])
            key = reason or "UNKNOWN_REJECTION"
            reasons[key] = int(reasons.get(key) or 0) + 1
            diagnostic["rejection_reasons"] = reasons
            continue
        diagnostic["accepted_count"] = int(diagnostic["accepted_count"]) + 1
        accepted[str(candidate["signal_id"])] = candidate
    return diagnostic, None


def _scent_score(primary: Mapping[str, Any], tier1: Mapping[str, Any] | None = None) -> int:
    if tier1 and int(tier1.get("accepted_count") or 0) > 0:
        return 100
    if tier1 and int(tier1.get("result_count") or 0) > 0:
        return 75
    if int(primary.get("result_count") or 0) > 0:
        reasons = primary.get("rejection_reasons") or {}
        if int(reasons.get("MARKET_SIGNAL_REJECTED") or 0) > 0:
            return 65
        return 50
    return 10


def _adaptive_limit(env: Mapping[str, str], explicit: int) -> int:
    raw = _compact(env.get("SE_DE_ADAPTIVE_MAX_REQUESTS"))
    value = explicit
    if raw:
        try:
            value = int(raw)
        except ValueError:
            value = explicit
    return max(0, min(MAX_ADAPTIVE_MAX_REQUESTS, value))


def collect_manifest_se_de_source_coverage_gap(
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
    observed_at: datetime | None = None,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory = _default_provider_factory,
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
    freshness: str | None = DEFAULT_FRESHNESS,
    adaptive_max_requests: int = DEFAULT_ADAPTIVE_MAX_REQUESTS,
) -> dict[str, Any]:
    """Run nine primary searches plus bounded adaptive expansion when needed."""
    if not 1 <= results_per_query <= MAX_RESULTS_PER_QUERY:
        raise ValueError(f"results_per_query must be between 1 and {MAX_RESULTS_PER_QUERY}")
    if not 0 <= adaptive_max_requests <= MAX_ADAPTIVE_MAX_REQUESTS:
        raise ValueError(f"adaptive_max_requests must be between 0 and {MAX_ADAPTIVE_MAX_REQUESTS}")

    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    env = environment if environment is not None else os.environ
    adaptive_budget = _adaptive_limit(env, adaptive_max_requests)
    api_key = _compact(env.get("BRAVE_SEARCH_API_KEY")) or _compact(env.get("BRAVE_API_KEY"))
    root_path = Path(root)
    market_reports: list[dict[str, Any]] = []
    providers: dict[str, SearchProvider] = {}
    primary_request_count = 0

    for market_code in SUPPORTED_MARKETS:
        source_queries = SOURCE_QUERIES[market_code]
        target = _target_spec(manifest, market_code)
        common: dict[str, Any] = {
            "source_country": market_code,
            "query_budget": len(source_queries),
            "queries_attempted": 0,
            "queries_succeeded": 0,
            "accepted_signal_count": 0,
            "rejected_result_count": 0,
            "duplicate_result_count": 0,
            "primary_accepted_signal_count": 0,
            "primary_rejected_result_count": 0,
            "primary_duplicate_result_count": 0,
            "adaptive_queries_attempted": 0,
            "adaptive_queries_succeeded": 0,
            "adaptive_signal_count": 0,
            "signals": [],
            "source_queries": [{"query_id": item.query_id, "source_name": item.source_name, "source_domain": item.source_domain, "source_role": item.source_role, "query": item.query} for item in source_queries],
            "query_diagnostics": [],
            "adaptive_query_diagnostics": [],
            "errors": [],
            **_safety_payload(),
        }
        if target is None:
            common.update(status="BLOCKED_CONFIGURATION", block_reason="MARKET_ARTIFACT_DIRECTORY_MISSING")
            common["coverage_health"] = _coverage_health(common)
            market_reports.append(common)
            continue
        if not api_key:
            common.update(status="BLOCKED_CONFIGURATION", block_reason="BRAVE_SEARCH_API_KEY_MISSING")
            common["coverage_health"] = _coverage_health(common)
            market_reports.append(common)
            continue
        try:
            provider = provider_factory(market_code, api_key, freshness)
            providers[market_code] = provider
        except Exception as exc:
            common.update(status="BLOCKED_RETRIEVAL", block_reason="PROVIDER_INITIALIZATION_FAILED", errors=[f"{type(exc).__name__}: {_compact(exc)[:300]}"])
            common["coverage_health"] = _coverage_health(common)
            market_reports.append(common)
            continue

        accepted: dict[str, dict[str, Any]] = {}
        seen_urls: set[str] = set()
        for item in source_queries:
            common["queries_attempted"] = int(common["queries_attempted"]) + 1
            primary_request_count += 1
            diagnostic, error = _run_query(provider, item, market_code=market_code, results_per_query=results_per_query, observed_at=now, seen_urls=seen_urls, accepted=accepted)
            if error:
                common["errors"].append(error)
            else:
                common["queries_succeeded"] = int(common["queries_succeeded"]) + 1
            common["query_diagnostics"].append(diagnostic)

        common["primary_accepted_signal_count"] = len(accepted)
        common["primary_rejected_result_count"] = sum(int(item.get("rejected_count") or 0) for item in common["query_diagnostics"])
        common["primary_duplicate_result_count"] = sum(int(item.get("duplicate_count") or 0) for item in common["query_diagnostics"])
        common["_accepted_map"] = accepted
        common["_seen_urls"] = seen_urls
        common["coverage_health"] = _coverage_health(common)
        common["_target"] = target
        market_reports.append(common)

    # Tier 1: one alternative for every source with zero accepted primary yield.
    tier1_candidates: list[tuple[str, AdaptiveExpansionQuery, Mapping[str, Any]]] = []
    for market_code in ("DE", "SE"):
        report = next((item for item in market_reports if item.get("source_country") == market_code), None)
        if not report or market_code not in providers:
            continue
        for diag in report.get("query_diagnostics") or []:
            if int(diag.get("accepted_count") or 0) > 0:
                continue
            family = EXPANSION_FAMILIES.get(str(diag.get("query_id")))
            if family:
                tier1_candidates.append((market_code, family[0], diag))

    adaptive_used = 0
    tier1_by_parent: dict[tuple[str, str], dict[str, Any]] = {}
    for market_code, item, primary_diag in tier1_candidates:
        if adaptive_used >= adaptive_budget:
            break
        report = next(entry for entry in market_reports if entry.get("source_country") == market_code)
        diagnostic, error = _run_query(providers[market_code], item, market_code=market_code, results_per_query=results_per_query, observed_at=now, seen_urls=report["_seen_urls"], accepted=report["_accepted_map"])
        adaptive_used += 1
        report["adaptive_queries_attempted"] = int(report["adaptive_queries_attempted"]) + 1
        if error:
            report["errors"].append(error)
        else:
            report["adaptive_queries_succeeded"] = int(report["adaptive_queries_succeeded"]) + 1
        diagnostic["trigger_reason"] = "PRIMARY_NO_ACCEPTED_SIGNAL"
        diagnostic["scent_score_before"] = _scent_score(primary_diag)
        report["adaptive_query_diagnostics"].append(diagnostic)
        tier1_by_parent[(market_code, item.parent_query_id)] = diagnostic

    # Tier 2: remaining budget follows the strongest scent only.
    tier2_candidates: list[tuple[int, int, str, AdaptiveExpansionQuery, Mapping[str, Any]]] = []
    for market_code in ("DE", "SE"):
        report = next((item for item in market_reports if item.get("source_country") == market_code), None)
        if not report or market_code not in providers:
            continue
        primary_by_id = {str(item.get("query_id")): item for item in report.get("query_diagnostics") or []}
        for parent_id, family in EXPANSION_FAMILIES.items():
            primary_diag = primary_by_id.get(parent_id)
            if not primary_diag or int(primary_diag.get("accepted_count") or 0) > 0:
                continue
            tier1_diag = tier1_by_parent.get((market_code, parent_id))
            score = _scent_score(primary_diag, tier1_diag)
            market_priority = 1 if market_code == "DE" else 0
            tier2_candidates.append((score, market_priority, market_code, family[1], primary_diag))
    tier2_candidates.sort(key=lambda row: (-row[0], -row[1], row[3].query_id))

    for score, _, market_code, item, _primary_diag in tier2_candidates:
        if adaptive_used >= adaptive_budget:
            break
        report = next(entry for entry in market_reports if entry.get("source_country") == market_code)
        diagnostic, error = _run_query(providers[market_code], item, market_code=market_code, results_per_query=results_per_query, observed_at=now, seen_urls=report["_seen_urls"], accepted=report["_accepted_map"])
        adaptive_used += 1
        report["adaptive_queries_attempted"] = int(report["adaptive_queries_attempted"]) + 1
        if error:
            report["errors"].append(error)
        else:
            report["adaptive_queries_succeeded"] = int(report["adaptive_queries_succeeded"]) + 1
        diagnostic["trigger_reason"] = "STRONGEST_SCENT_FOLLOW_UP"
        diagnostic["scent_score_before"] = score
        report["adaptive_query_diagnostics"].append(diagnostic)

    status_counts: dict[str, int] = {}
    adaptive_signal_count = 0
    rescued_sources = 0
    for report in market_reports:
        accepted = report.pop("_accepted_map", {})
        report.pop("_seen_urls", None)
        target = report.pop("_target", None)
        primary_count = int(report.get("primary_accepted_signal_count") or 0)
        total_count = len(accepted)
        adaptive_count = max(0, total_count - primary_count)
        report["adaptive_signal_count"] = adaptive_count
        report["accepted_signal_count"] = total_count
        report["rejected_result_count"] = int(report.get("primary_rejected_result_count") or 0) + sum(int(item.get("rejected_count") or 0) for item in report.get("adaptive_query_diagnostics") or [])
        report["duplicate_result_count"] = int(report.get("primary_duplicate_result_count") or 0) + sum(int(item.get("duplicate_count") or 0) for item in report.get("adaptive_query_diagnostics") or [])
        report["signals"] = [accepted[key] for key in sorted(accepted)]
        adaptive_signal_count += adaptive_count
        primary_diag_by_id = {str(item.get("query_id")): item for item in report.get("query_diagnostics") or []}
        for diag in report.get("adaptive_query_diagnostics") or []:
            if int(diag.get("accepted_count") or 0) > 0 and int(primary_diag_by_id.get(str(diag.get("parent_query_id")), {}).get("accepted_count") or 0) == 0:
                rescued_sources += 1
        if report.get("block_reason"):
            status = str(report.get("status") or "BLOCKED")
        elif report.get("errors"):
            status = "PARTIAL_RETRIEVAL" if int(report.get("queries_succeeded") or 0) else "BLOCKED_RETRIEVAL"
        else:
            status = "SUCCESS" if total_count else "VALID_ZERO"
        report["status"] = status
        report["block_reason"] = report.get("block_reason")
        report["coverage_health"] = _coverage_health(report)
        report["adaptive_health"] = {
            "version": ADAPTIVE_SEARCH_EXPANSION_VERSION,
            "adaptive_queries_attempted": report.get("adaptive_queries_attempted", 0),
            "adaptive_queries_succeeded": report.get("adaptive_queries_succeeded", 0),
            "adaptive_signal_count": adaptive_count,
            "combined_signal_count": total_count,
            "adaptive_yield_per_query": _ratio(adaptive_count, int(report.get("adaptive_queries_succeeded") or 0)),
            "diagnosis": "ADAPTIVE_RESCUE_SUCCESS" if adaptive_count else ("PRIMARY_SIGNAL_FLOWING" if primary_count else "ADAPTIVE_SEARCH_EXHAUSTED"),
        }
        if target is not None:
            artifact_dir = root_path / _compact(target.get("artifact_dir"))
            report_path = artifact_dir / _compact(target.get("market_signal_report_file") or "market-signal-report.json")
            report["stored_signal_count"] = _write_merged_market_signal_report(report_path, market_code=str(report.get("source_country")), signals=report["signals"], observed_at=now)
            report["artifact_path"] = report_path.relative_to(root_path).as_posix()
        status_counts[status] = status_counts.get(status, 0) + 1

    coverage_health = {str(report.get("source_country")): report.get("coverage_health") or _coverage_health(report) for report in market_reports}
    source_yield_diagnostics = {str(report.get("source_country")): report.get("query_diagnostics") or [] for report in market_reports}
    adaptive_diagnostics = {str(report.get("source_country")): report.get("adaptive_query_diagnostics") or [] for report in market_reports}
    total_signals = sum(int(report.get("accepted_signal_count") or 0) for report in market_reports)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso_utc(now),
        "feed_family": FEED_FAMILY,
        "purpose": "TARGETED_SE_DE_CLOTHING_LIQUIDATION_SOURCE_COVERAGE",
        "market_coverage": list(SUPPORTED_MARKETS),
        "query_budget_total": sum(len(SOURCE_QUERIES[m]) for m in SUPPORTED_MARKETS),
        "requests_made": primary_request_count,
        "combined_requests_made": primary_request_count + adaptive_used,
        "adaptive_search_expansion_version": ADAPTIVE_SEARCH_EXPANSION_VERSION,
        "adaptive_query_budget_total": adaptive_budget,
        "adaptive_requests_made": adaptive_used,
        "adaptive_requests_remaining": max(0, adaptive_budget - adaptive_used),
        "adaptive_signal_count": adaptive_signal_count,
        "adaptive_rescued_source_count": rescued_sources,
        "results_per_query": results_per_query,
        "freshness": freshness,
        "status_counts": status_counts,
        "signal_count": total_signals,
        "coverage_health_version": COVERAGE_HEALTH_VERSION,
        "coverage_health": coverage_health,
        "source_yield_diagnostics_version": SOURCE_YIELD_DIAGNOSTICS_VERSION,
        "source_yield_diagnostics": source_yield_diagnostics,
        "adaptive_query_diagnostics": adaptive_diagnostics,
        "sources": market_reports,
        "source_page_verification_required": True,
        **_safety_payload(),
    }
