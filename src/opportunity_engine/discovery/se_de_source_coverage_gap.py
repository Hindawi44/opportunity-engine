"""Targeted Sweden/Germany source-coverage radar for clothing liquidation.

This bounded feed supplements the broad market radar with source-specific
searches for public auction, liquidation, and early insolvency pages that have
demonstrated relevance to clothing stock in Sweden and Germany. Search hits are
signals only and must still pass source-page verification before any commercial
decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
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

SCHEMA_VERSION = "se-de-source-coverage-gap-1.5"
FEED_FAMILY = "SE_DE_SOURCE_COVERAGE_GAP_V1"
COVERAGE_HEALTH_VERSION = "SE_DE_COVERAGE_HEALTH_V1"
SOURCE_YIELD_DIAGNOSTICS_VERSION = "SE_DE_SOURCE_YIELD_DIAGNOSTICS_V1"
SUPPORTED_MARKETS = ("SE", "DE")
DEFAULT_RESULTS_PER_QUERY = 8
MAX_RESULTS_PER_QUERY = 10
DEFAULT_FRESHNESS = "pm"

ProviderFactory = Callable[[str, str, str | None], SearchProvider]


@dataclass(frozen=True, slots=True)
class CoverageSourceQuery:
    query_id: str
    source_name: str
    source_domain: str
    query: str
    source_role: str = "DIRECT_SALE_OR_AUCTION_SOURCE"


SOURCE_QUERIES: dict[str, tuple[CoverageSourceQuery, ...]] = {
    "SE": (
        CoverageSourceQuery(
            "se-budi-bankruptcy-clothing",
            "Budi Auktioner",
            "budi.se",
            'site:budi.se (konkursauktion OR konkurslager OR varulager OR utförsäljning) (kläder OR skor OR textil OR mode)',
        ),
        CoverageSourceQuery(
            "se-kronofogden-varuparti-clothing",
            "Kronofogden Webauktion",
            "auktion.kronofogden.se",
            'site:auktion.kronofogden.se ("Varuparti" OR "Konkurslager" OR kläder OR skor) (auktion OR försäljning)',
        ),
        CoverageSourceQuery(
            "se-psauction-bankruptcy-clothing-stock",
            "PS Auction",
            "psauction.se",
            'site:psauction.se (konkurs OR konkursauktion OR varulager OR "parti med") (kläder OR skor OR mode OR textil)',
        ),
        CoverageSourceQuery(
            "se-klaravik-bankruptcy-clothing-stock",
            "Klaravik",
            "klaravik.se",
            'site:klaravik.se (konkursbo OR konkurs OR varulager OR konkursparti) (kläder OR märkeskläder OR skor OR klädbutik)',
        ),
        CoverageSourceQuery(
            "se-allabolag-clothing-insolvency",
            "Allabolag",
            "allabolag.se",
            'site:allabolag.se/foretag ("Konkurs inledd") (kläder OR konfektion OR skodon OR mode OR textilier)',
            "EARLY_INSOLVENCY_SIGNAL_SOURCE",
        ),
    ),
    "DE": (
        CoverageSourceQuery(
            "de-htkg-insolvency-fashion",
            "HTKG Online-Versteigerungen",
            "online-versteigerungen.ht-kg.de",
            'site:online-versteigerungen.ht-kg.de (Insolvenzversteigerung OR Warenbestand) (Mode OR Bekleidung OR Textil OR Kleidung)',
        ),
        CoverageSourceQuery(
            "de-sen-sen-textile-liquidation",
            "Sen & Sen",
            "sen-sen.de",
            'site:sen-sen.de (Liquidationsverkauf OR Insolvenz OR Warenbestand) (Textil OR Bekleidung OR Arbeitskleidung OR Mode)',
        ),
        CoverageSourceQuery(
            "de-restlos-insolvency-clothing-stock",
            "RESTLOS",
            "restlos.com",
            'site:restlos.com (Insolvenzauktion OR Insolvenzversteigerung OR Warenbestand) (Bekleidung OR Mode OR Textil OR Sportbekleidung)',
        ),
        CoverageSourceQuery(
            "de-versteigerungskalender-fashion-insolvency",
            "Versteigerungskalender",
            "versteigerungskalender.de",
            'site:versteigerungskalender.de/insolvenzkalender (Insolvenzeröffnung OR Insolvenz) (Textilhandel OR Bekleidung OR Mode OR Schuhe)',
            "EARLY_INSOLVENCY_SIGNAL_SOURCE",
        ),
    ),
}

_COMMON_CLOTHING_TERMS = (
    "clothing",
    "fashion",
    "apparel",
    "garment",
    "garments",
    "footwear",
)
_MARKET_CLOTHING_TERMS: dict[str, tuple[str, ...]] = {
    "SE": (
        "kläder",
        "klader",
        "kläd",
        "klad",
        "skor",
        "textil",
        "mode",
        "märkeskläder",
        "markesklader",
        "klädbutik",
        "kladbutik",
        "konfektion",
        "skodon",
        "textilier",
        "plagg",
        "accessoar",
    ),
    "DE": (
        "bekleidung",
        "kleidung",
        "textil",
        "mode",
        "schuhe",
        "schuh",
        "sportbekleidung",
        "arbeitskleidung",
        "konfektion",
        "warenbestand mode",
    ),
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


def _radar_query(item: CoverageSourceQuery) -> MarketRadarQuery:
    return MarketRadarQuery(query_id=item.query_id, query=item.query)


def _hit_text(hit: SearchHit) -> str:
    return " ".join(
        (
            _compact(getattr(hit, "title", "")),
            _compact(getattr(hit, "description", "")),
            _compact(getattr(hit, "url", "")),
        )
    ).casefold()


def _has_clothing_relevance(hit: SearchHit, market_code: str) -> bool:
    text = _hit_text(hit)
    terms = _COMMON_CLOTHING_TERMS + _MARKET_CLOTHING_TERMS.get(
        market_code.upper(), ()
    )
    return any(term.casefold() in text for term in terms)


def _candidate_from_hit_with_reason(
    hit: SearchHit,
    *,
    market_code: str,
    source_query: CoverageSourceQuery,
    rank: int,
    observed_at: datetime,
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(hit, SearchHit):
        return None, "INVALID_HIT"
    if not _approved_domain(_compact(hit.url), source_query.source_domain):
        return None, "UNAPPROVED_DOMAIN"
    if not _has_clothing_relevance(hit, market_code):
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
    payload["metadata"] = metadata
    return payload, None


def _candidate_from_hit(
    hit: SearchHit,
    *,
    market_code: str,
    source_query: CoverageSourceQuery,
    rank: int,
    observed_at: datetime,
) -> dict[str, Any] | None:
    candidate, _ = _candidate_from_hit_with_reason(
        hit,
        market_code=market_code,
        source_query=source_query,
        rank=rank,
        observed_at=observed_at,
    )
    return candidate


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 3)


def _coverage_health(report: Mapping[str, Any]) -> dict[str, Any]:
    query_budget = int(report.get("query_budget") or 0)
    attempted = int(report.get("queries_attempted") or 0)
    succeeded = int(report.get("queries_succeeded") or 0)
    accepted = int(report.get("accepted_signal_count") or 0)
    rejected = int(report.get("rejected_result_count") or 0)
    duplicates = int(report.get("duplicate_result_count") or 0)
    source_queries = [
        item
        for item in (report.get("source_queries") or [])
        if isinstance(item, Mapping)
    ]
    query_diagnostics = [
        item
        for item in (report.get("query_diagnostics") or [])
        if isinstance(item, Mapping)
    ]
    source_roles = sorted(
        {str(item.get("source_role") or "UNKNOWN") for item in source_queries}
    )
    direct_source_count = sum(
        1
        for item in source_queries
        if item.get("source_role") == "DIRECT_SALE_OR_AUCTION_SOURCE"
    )
    early_source_count = sum(
        1
        for item in source_queries
        if item.get("source_role") == "EARLY_INSOLVENCY_SIGNAL_SOURCE"
    )
    retrieval_rate = _ratio(succeeded, query_budget)
    observed_result_count = accepted + rejected + duplicates
    rejection_rate = _ratio(rejected, accepted + rejected)
    signal_yield_per_successful_query = _ratio(accepted, succeeded)
    productive_source_count = sum(
        1 for item in query_diagnostics if int(item.get("accepted_count") or 0) > 0
    )
    result_bearing_source_count = sum(
        1 for item in query_diagnostics if int(item.get("result_count") or 0) > 0
    )
    zero_result_source_count = sum(
        1
        for item in query_diagnostics
        if item.get("search_status") == "SUCCESS"
        and int(item.get("result_count") or 0) == 0
    )
    relevance_rejection_count = sum(
        int(
            (item.get("rejection_reasons") or {}).get(
                "CLOTHING_RELEVANCE_MISSING"
            )
            or 0
        )
        for item in query_diagnostics
    )

    if attempted == 0 or succeeded == 0:
        diagnosis = "RETRIEVAL_BLOCKED"
    elif retrieval_rate < 0.8:
        diagnosis = "RETRIEVAL_GAP"
    elif accepted == 0 and observed_result_count == 0:
        diagnosis = "HEALTHY_ZERO_SIGNAL"
    elif accepted == 0:
        diagnosis = "RESULTS_SEEN_BUT_NONE_ACCEPTED"
    elif signal_yield_per_successful_query < 0.25:
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
        "observed_result_count": observed_result_count,
        "rejection_rate": rejection_rate,
        "signal_yield_per_successful_query": signal_yield_per_successful_query,
        "source_count": len(source_queries),
        "direct_sale_or_auction_source_count": direct_source_count,
        "early_insolvency_source_count": early_source_count,
        "source_role_diversity": source_roles,
        "productive_source_count": productive_source_count,
        "productive_source_rate": _ratio(productive_source_count, query_budget),
        "result_bearing_source_count": result_bearing_source_count,
        "zero_result_source_count": zero_result_source_count,
        "clothing_relevance_rejection_count": relevance_rejection_count,
        "diagnosis": diagnosis,
    }


def collect_manifest_se_de_source_coverage_gap(
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
    observed_at: datetime | None = None,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory = _default_provider_factory,
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
    freshness: str | None = DEFAULT_FRESHNESS,
) -> dict[str, Any]:
    """Run nine bounded source-specific searches and merge accepted signals."""
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
    root_path = Path(root)
    market_reports: list[dict[str, Any]] = []
    request_count = 0

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
            "signals": [],
            "source_queries": [
                {
                    "query_id": item.query_id,
                    "source_name": item.source_name,
                    "source_domain": item.source_domain,
                    "source_role": item.source_role,
                    "query": item.query,
                }
                for item in source_queries
            ],
            "query_diagnostics": [],
            "errors": [],
            **_safety_payload(),
        }
        if target is None:
            common.update(
                status="BLOCKED_CONFIGURATION",
                block_reason="MARKET_ARTIFACT_DIRECTORY_MISSING",
            )
            common["coverage_health"] = _coverage_health(common)
            market_reports.append(common)
            continue
        if not api_key:
            common.update(
                status="BLOCKED_CONFIGURATION",
                block_reason="BRAVE_SEARCH_API_KEY_MISSING",
            )
            common["coverage_health"] = _coverage_health(common)
            market_reports.append(common)
            continue

        try:
            provider = provider_factory(market_code, api_key, freshness)
        except Exception as exc:
            common.update(
                status="BLOCKED_RETRIEVAL",
                block_reason="PROVIDER_INITIALIZATION_FAILED",
                errors=[f"{type(exc).__name__}: {_compact(exc)[:300]}"],
            )
            common["coverage_health"] = _coverage_health(common)
            market_reports.append(common)
            continue

        accepted: dict[str, dict[str, Any]] = {}
        seen_urls: set[str] = set()
        errors: list[str] = []
        rejected = duplicates = succeeded = 0

        for source_query in source_queries:
            common["queries_attempted"] = int(common["queries_attempted"]) + 1
            request_count += 1
            query_diagnostic: dict[str, Any] = {
                "query_id": source_query.query_id,
                "source_name": source_query.source_name,
                "source_domain": source_query.source_domain,
                "source_role": source_query.source_role,
                "search_status": "SUCCESS",
                "result_count": 0,
                "accepted_count": 0,
                "rejected_count": 0,
                "duplicate_count": 0,
                "rejection_reasons": {},
            }

            try:
                hits = provider.search(
                    source_query.query, count=results_per_query
                )
                succeeded += 1
                query_diagnostic["result_count"] = len(hits)
            except Exception as exc:
                message = (
                    f"{source_query.query_id}: {type(exc).__name__}: "
                    f"{_compact(exc)[:300]}"
                )
                errors.append(message)
                query_diagnostic["search_status"] = "ERROR"
                query_diagnostic["error"] = message
                common["query_diagnostics"].append(query_diagnostic)
                continue

            for rank, hit in enumerate(hits, start=1):
                raw_url = _compact(getattr(hit, "url", ""))
                if raw_url in seen_urls:
                    duplicates += 1
                    query_diagnostic["duplicate_count"] = (
                        int(query_diagnostic["duplicate_count"]) + 1
                    )
                    continue
                if raw_url:
                    seen_urls.add(raw_url)

                candidate, rejection_reason = _candidate_from_hit_with_reason(
                    hit,
                    market_code=market_code,
                    source_query=source_query,
                    rank=rank,
                    observed_at=now,
                )
                if candidate is None:
                    rejected += 1
                    query_diagnostic["rejected_count"] = (
                        int(query_diagnostic["rejected_count"]) + 1
                    )
                    reason = rejection_reason or "UNKNOWN_REJECTION"
                    reasons = dict(query_diagnostic["rejection_reasons"])
                    reasons[reason] = int(reasons.get(reason) or 0) + 1
                    query_diagnostic["rejection_reasons"] = reasons
                    continue

                query_diagnostic["accepted_count"] = (
                    int(query_diagnostic["accepted_count"]) + 1
                )
                accepted[str(candidate["signal_id"])] = candidate

            common["query_diagnostics"].append(query_diagnostic)

        common["queries_succeeded"] = succeeded
        common["accepted_signal_count"] = len(accepted)
        common["rejected_result_count"] = rejected
        common["duplicate_result_count"] = duplicates
        common["signals"] = [accepted[key] for key in sorted(accepted)]
        common["errors"] = errors
        common["status"] = (
            ("PARTIAL_RETRIEVAL" if succeeded else "BLOCKED_RETRIEVAL")
            if errors
            else ("SUCCESS" if accepted else "VALID_ZERO")
        )
        common["block_reason"] = None
        common["coverage_health"] = _coverage_health(common)

        artifact_dir = root_path / _compact(target.get("artifact_dir"))
        report_path = artifact_dir / _compact(
            target.get("market_signal_report_file")
            or "market-signal-report.json"
        )
        common["stored_signal_count"] = _write_merged_market_signal_report(
            report_path,
            market_code=market_code,
            signals=common["signals"],
            observed_at=now,
        )
        common["artifact_path"] = report_path.relative_to(root_path).as_posix()
        market_reports.append(common)

    status_counts: dict[str, int] = {}
    for report in market_reports:
        status = _compact(report.get("status")).upper() or "UNKNOWN"
        status_counts[status] = status_counts.get(status, 0) + 1

    coverage_health = {
        str(report.get("source_country")): report.get("coverage_health")
        or _coverage_health(report)
        for report in market_reports
    }
    source_yield_diagnostics = {
        str(report.get("source_country")): report.get("query_diagnostics") or []
        for report in market_reports
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso_utc(now),
        "feed_family": FEED_FAMILY,
        "purpose": "TARGETED_SE_DE_CLOTHING_LIQUIDATION_SOURCE_COVERAGE",
        "market_coverage": list(SUPPORTED_MARKETS),
        "query_budget_total": sum(
            len(SOURCE_QUERIES[m]) for m in SUPPORTED_MARKETS
        ),
        "requests_made": request_count,
        "results_per_query": results_per_query,
        "freshness": freshness,
        "status_counts": status_counts,
        "signal_count": sum(
            int(report.get("accepted_signal_count") or 0)
            for report in market_reports
        ),
        "coverage_health_version": COVERAGE_HEALTH_VERSION,
        "coverage_health": coverage_health,
        "source_yield_diagnostics_version": SOURCE_YIELD_DIAGNOSTICS_VERSION,
        "source_yield_diagnostics": source_yield_diagnostics,
        "sources": market_reports,
        "source_page_verification_required": True,
        **_safety_payload(),
    }
