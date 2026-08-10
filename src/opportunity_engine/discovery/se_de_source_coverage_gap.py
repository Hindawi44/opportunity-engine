"""Targeted Sweden/Germany source-coverage radar for clothing liquidation.

This bounded feed supplements the broad market radar with source-specific
searches for public auction/liquidation pages that have demonstrated relevance
to clothing stock in Sweden and Germany. It produces market signals only;
source pages must still be verified before any commercial decision.
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

SCHEMA_VERSION = "se-de-source-coverage-gap-1.0"
FEED_FAMILY = "SE_DE_SOURCE_COVERAGE_GAP_V1"
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


SOURCE_QUERIES: dict[str, tuple[CoverageSourceQuery, ...]] = {
    "SE": (
        CoverageSourceQuery(
            query_id="se-budi-bankruptcy-clothing",
            source_name="Budi Auktioner",
            source_domain="budi.se",
            query=(
                'site:budi.se (konkursauktion OR konkurslager OR varulager OR '
                'utförsäljning) (kläder OR skor OR textil OR mode)'
            ),
        ),
        CoverageSourceQuery(
            query_id="se-kronofogden-varuparti-clothing",
            source_name="Kronofogden Webauktion",
            source_domain="auktion.kronofogden.se",
            query=(
                'site:auktion.kronofogden.se ("Varuparti" OR "Konkurslager" OR '
                'kläder OR skor) (auktion OR försäljning)'
            ),
        ),
    ),
    "DE": (
        CoverageSourceQuery(
            query_id="de-htkg-insolvency-fashion",
            source_name="HTKG Online-Versteigerungen",
            source_domain="online-versteigerungen.ht-kg.de",
            query=(
                'site:online-versteigerungen.ht-kg.de (Insolvenzversteigerung OR '
                'Warenbestand) (Mode OR Bekleidung OR Textil OR Kleidung)'
            ),
        ),
        CoverageSourceQuery(
            query_id="de-sen-sen-textile-liquidation",
            source_name="Sen & Sen",
            source_domain="sen-sen.de",
            query=(
                'site:sen-sen.de (Liquidationsverkauf OR Insolvenz OR Warenbestand) '
                '(Textil OR Bekleidung OR Arbeitskleidung OR Mode)'
            ),
        ),
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


def _candidate_from_hit(
    hit: SearchHit,
    *,
    market_code: str,
    source_query: CoverageSourceQuery,
    rank: int,
    observed_at: datetime,
) -> dict[str, Any] | None:
    if not isinstance(hit, SearchHit):
        return None
    if not _approved_domain(_compact(hit.url), source_query.source_domain):
        return None
    signal = market_signal_from_brave_hit(
        hit,
        market_code=market_code,
        query=_radar_query(source_query),
        rank=rank,
        observed_at=observed_at,
    )
    if signal is None:
        return None
    payload = signal.model_dump(mode="json")
    payload["source"] = "SE/DE source coverage gap radar"
    metadata = dict(payload.get("metadata") or {})
    metadata.update(
        {
            "coverage_gap_feed_family": FEED_FAMILY,
            "coverage_gap_source_name": source_query.source_name,
            "coverage_gap_source_domain": source_query.source_domain,
            "source_page_verification_required": True,
            "promotion_to_opportunity_allowed": False,
        }
    )
    payload["metadata"] = metadata
    return payload


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
    """Run four bounded source-specific searches and merge accepted signals."""
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
                    "query": item.query,
                }
                for item in source_queries
            ],
            "errors": [],
            **_safety_payload(),
        }
        if target is None:
            common.update(
                status="BLOCKED_CONFIGURATION",
                block_reason="MARKET_ARTIFACT_DIRECTORY_MISSING",
            )
            market_reports.append(common)
            continue
        if not api_key:
            common.update(
                status="BLOCKED_CONFIGURATION",
                block_reason="BRAVE_SEARCH_API_KEY_MISSING",
            )
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
            market_reports.append(common)
            continue

        accepted: dict[str, dict[str, Any]] = {}
        seen_urls: set[str] = set()
        errors: list[str] = []
        rejected = 0
        duplicates = 0
        succeeded = 0
        for source_query in source_queries:
            common["queries_attempted"] = int(common["queries_attempted"]) + 1
            request_count += 1
            try:
                hits = provider.search(source_query.query, count=results_per_query)
                succeeded += 1
            except Exception as exc:
                errors.append(
                    f"{source_query.query_id}: {type(exc).__name__}: {_compact(exc)[:300]}"
                )
                continue
            for rank, hit in enumerate(hits, start=1):
                raw_url = _compact(getattr(hit, "url", ""))
                if raw_url in seen_urls:
                    duplicates += 1
                    continue
                if raw_url:
                    seen_urls.add(raw_url)
                candidate = _candidate_from_hit(
                    hit,
                    market_code=market_code,
                    source_query=source_query,
                    rank=rank,
                    observed_at=now,
                )
                if candidate is None:
                    rejected += 1
                    continue
                accepted[str(candidate["signal_id"])] = candidate

        common["queries_succeeded"] = succeeded
        common["accepted_signal_count"] = len(accepted)
        common["rejected_result_count"] = rejected
        common["duplicate_result_count"] = duplicates
        common["signals"] = [accepted[key] for key in sorted(accepted)]
        common["errors"] = errors
        if errors:
            common["status"] = "PARTIAL_RETRIEVAL" if succeeded else "BLOCKED_RETRIEVAL"
        else:
            common["status"] = "SUCCESS" if accepted else "VALID_ZERO"
        common["block_reason"] = None

        artifact_dir = root_path / _compact(target.get("artifact_dir"))
        report_path = artifact_dir / _compact(
            target.get("market_signal_report_file") or "market-signal-report.json"
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

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso_utc(now),
        "feed_family": FEED_FAMILY,
        "purpose": "TARGETED_SE_DE_CLOTHING_LIQUIDATION_SOURCE_COVERAGE",
        "market_coverage": list(SUPPORTED_MARKETS),
        "query_budget_total": sum(len(SOURCE_QUERIES[m]) for m in SUPPORTED_MARKETS),
        "requests_made": request_count,
        "results_per_query": results_per_query,
        "freshness": freshness,
        "status_counts": status_counts,
        "signal_count": sum(
            int(report.get("accepted_signal_count") or 0) for report in market_reports
        ),
        "sources": market_reports,
        "source_page_verification_required": True,
        **_safety_payload(),
    }
