"""English-language companion search for the bounded bridal liquidation feed.

The existing local-language bridal searches remain authoritative for Norway,
Sweden, and Germany. This module adds one English query for each same market so
international, wholesale, and cross-border pages can enter the same market-
intelligence river. Search snippets remain unverified early signals only.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from opportunity_engine.discovery import bridal_liquidation_feed as local_feed
from opportunity_engine.discovery.brave_market_signal_radar import (
    _canonical_url,
    _compact,
    _default_provider_factory,
    _iso_utc,
    _target_spec,
    _write_merged_market_signal_report,
)
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.market_intelligence import (
    MarketSignalRecord,
    MarketSignalStatus,
    MarketSignalType,
)
from opportunity_engine.unified_models import Evidence


SCHEMA_VERSION = "bridal-bilingual-market-search-1.0"
ENGLISH_SEARCH_LANE = "ENGLISH_MARKET_SEARCH_V1"
SUPPORTED_MARKETS = local_feed.SUPPORTED_MARKETS
DEFAULT_RESULTS_PER_QUERY = local_feed.DEFAULT_RESULTS_PER_QUERY
MAX_RESULTS_PER_QUERY = local_feed.MAX_RESULTS_PER_QUERY
DEFAULT_FRESHNESS = local_feed.DEFAULT_FRESHNESS
ProviderFactory = local_feed.ProviderFactory
_ORIGINAL_LOCAL_COLLECTOR = local_feed.collect_manifest_bridal_liquidation_signals


@dataclass(frozen=True, slots=True)
class EnglishBridalQuery:
    query_id: str
    query: str
    language: str = "en"
    lane: str = ENGLISH_SEARCH_LANE


ENGLISH_BRIDAL_QUERIES: dict[str, EnglishBridalQuery] = {
    "NO": EnglishBridalQuery(
        "no-bridal-liquidation-en",
        '("bridal shop liquidation" OR "bridal boutique closing down" OR '
        '"wedding dress stock clearance" OR "bridal inventory lot" OR '
        '"sample wedding dresses") (Norway OR Norwegian)',
    ),
    "SE": EnglishBridalQuery(
        "se-bridal-liquidation-en",
        '("bridal shop liquidation" OR "bridal boutique closing down" OR '
        '"wedding dress stock clearance" OR "bridal inventory lot" OR '
        '"sample wedding dresses") (Sweden OR Swedish)',
    ),
    "DE": EnglishBridalQuery(
        "de-bridal-liquidation-en",
        '("bridal shop liquidation" OR "bridal boutique closing down" OR '
        '"wedding dress stock clearance" OR "bridal inventory lot" OR '
        '"sample wedding dresses") (Germany OR German)',
    ),
}

_ENGLISH_BRIDAL_TERMS = (
    "wedding dress",
    "wedding dresses",
    "bridal gown",
    "bridal gowns",
    "bridal shop",
    "bridal store",
    "bridal boutique",
    "bridal collection",
    "sample wedding dress",
    "sample wedding dresses",
    "sample bridal gown",
    "sample bridal gowns",
)
_ENGLISH_COMMERCIAL_BATCH_TERMS = (
    "wedding dresses",
    "bridal gowns",
    "bridal shop",
    "bridal store",
    "bridal boutique",
    "bridal collection",
    "sample wedding dresses",
    "sample bridal gowns",
    "inventory",
    "stock",
    "stocklot",
    "stock lot",
    "inventory lot",
    "batch",
    "collection",
    "warehouse",
)
_ENGLISH_INSOLVENCY_TERMS = (
    "insolvency",
    "bankruptcy",
    "liquidation",
    "liquidator",
    "insolvent",
)
_ENGLISH_CLOSURE_TERMS = (
    "closing down",
    "store closure",
    "shop closure",
    "business closure",
    "closing sale",
    "clearance sale",
    "closeout sale",
)
_ENGLISH_SURPLUS_TERMS = (
    "stock clearance",
    "inventory clearance",
    "warehouse stock",
    "surplus stock",
    "stocklot",
    "stock lot",
    "inventory lot",
    "sample wedding dresses",
    "sample bridal gowns",
)
_ENGLISH_AUCTION_TERMS = (
    "liquidation auction",
    "asset auction",
    "asset sale",
    "auction",
)


def _safety_payload() -> dict[str, bool]:
    return {
        "promotion_to_opportunity_allowed": False,
        "analysis_eligible": False,
        "top5_eligible": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _matched_terms(text: str, terms: Sequence[str]) -> list[str]:
    folded = text.casefold()
    return [term for term in terms if term.casefold() in folded]


def _classify_english_event(
    text: str,
) -> tuple[MarketSignalType | None, list[str]]:
    categories = (
        (MarketSignalType.INSOLVENCY_OR_LIQUIDATION, _ENGLISH_INSOLVENCY_TERMS),
        (MarketSignalType.BUSINESS_CLOSURE, _ENGLISH_CLOSURE_TERMS),
        (MarketSignalType.WAREHOUSE_SURPLUS, _ENGLISH_SURPLUS_TERMS),
        (MarketSignalType.AUCTION_EVENT, _ENGLISH_AUCTION_TERMS),
    )
    for signal_type, terms in categories:
        matched = _matched_terms(text, terms)
        if matched:
            return signal_type, matched
    return None, []


def english_bridal_signal_from_hit(
    hit: SearchHit,
    *,
    market_code: str,
    query: EnglishBridalQuery,
    observed_at: datetime,
) -> MarketSignalRecord | None:
    """Accept an English commercial bridal event, never a lone private dress."""
    market = market_code.upper()
    if market not in SUPPORTED_MARKETS:
        raise ValueError(f"unsupported market: {market}")
    if not isinstance(hit, SearchHit):
        return None

    title = _compact(hit.title)
    description = _compact(hit.description)
    if not title:
        return None
    combined = f"{title} {description}".strip()

    bridal_terms = _matched_terms(combined, _ENGLISH_BRIDAL_TERMS)
    batch_terms = _matched_terms(combined, _ENGLISH_COMMERCIAL_BATCH_TERMS)
    signal_type, event_terms = _classify_english_event(combined)
    if not bridal_terms or not batch_terms or signal_type is None:
        return None

    canonical_url = _canonical_url(_compact(hit.url))
    digest = sha256(canonical_url.encode("utf-8")).hexdigest()[:24]
    # The same canonical identity is deliberately shared with the local lane so
    # one page discovered in two languages remains one durable market signal.
    signal_id = f"bridal-feed:{market.casefold()}:{digest}"
    evidence = Evidence(
        evidence_type="BRAVE_SEARCH_RESULT",
        value=combined[:4000],
        source_url=canonical_url,
        captured_at=None,
        verified=False,
        metadata={
            "feed_family": local_feed.FEED_FAMILY,
            "query_id": query.query_id,
            "search_language": query.language,
            "search_lane": query.lane,
            "provider": _compact(hit.provider) or "Brave Search",
            "verification_status": "UNVERIFIED_PUBLIC_WEB",
        },
    )
    confidence = 0.60
    if any(term.casefold() in title.casefold() for term in bridal_terms):
        confidence += 0.05
    if any(term.casefold() in title.casefold() for term in event_terms):
        confidence += 0.05
    if len(set(batch_terms)) > 1:
        confidence += 0.03

    return MarketSignalRecord(
        signal_id=signal_id,
        signal_type=signal_type,
        value=(description or title)[:500],
        source="Brave Search bridal liquidation feed",
        observed_at=observed_at,
        confidence=min(0.73, confidence),
        source_country=market,
        source_url=canonical_url,
        title=title[:1000],
        company_name=None,
        seller_name=None,
        location=None,
        first_observed_at=observed_at,
        latest_observed_at=observed_at,
        event_date=None,
        evidence=[evidence],
        related_opportunity_id=None,
        status=MarketSignalStatus.WATCH,
        metadata={
            "signal_only": True,
            "not_an_opportunity": True,
            "feed_family": local_feed.FEED_FAMILY,
            "inventory_domain": "BRIDAL",
            "commercial_batch_gate": True,
            "discovery_transport": "BRAVE_SEARCH",
            "verification_status": "UNVERIFIED_PUBLIC_WEB",
            "query_id": query.query_id,
            "search_language": query.language,
            "search_lane": query.lane,
            "bridal_terms": sorted(set(bridal_terms)),
            "commercial_batch_terms": sorted(set(batch_terms)),
            "event_terms": sorted(set(event_terms)),
            "canonical_url": canonical_url,
            **_safety_payload(),
        },
    )


def collect_manifest_english_bridal_signals(
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
    observed_at: datetime | None = None,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory = _default_provider_factory,
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
    freshness: str | None = DEFAULT_FRESHNESS,
) -> dict[str, Any]:
    """Run one English bridal-market query in each existing country."""
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
    sources: list[dict[str, Any]] = []
    requests_made = 0

    for market_code in SUPPORTED_MARKETS:
        target = _target_spec(manifest, market_code)
        query = ENGLISH_BRIDAL_QUERIES[market_code]
        source: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "feed_family": local_feed.FEED_FAMILY,
            "search_lane": ENGLISH_SEARCH_LANE,
            "search_language": "en",
            "source": "Brave Search bridal liquidation feed",
            "source_country": market_code,
            "freshness": freshness,
            "query_id": query.query_id,
            "query": query.query,
            "query_budget": 1,
            "results_per_query": results_per_query,
            "queries_attempted": 0,
            "queries_succeeded": 0,
            "accepted_signal_count": 0,
            "rejected_result_count": 0,
            "duplicate_result_count": 0,
            "signals": [],
            "errors": [],
            **_safety_payload(),
        }
        if target is None:
            source["status"] = "BLOCKED_CONFIGURATION"
            source["block_reason"] = "MARKET_ARTIFACT_DIRECTORY_MISSING"
            sources.append(source)
            continue
        if not api_key:
            source["status"] = "BLOCKED_CONFIGURATION"
            source["block_reason"] = "BRAVE_SEARCH_API_KEY_MISSING"
            sources.append(source)
            continue

        try:
            provider = provider_factory(market_code, api_key, freshness)
        except Exception as exc:
            source["status"] = "BLOCKED_RETRIEVAL"
            source["block_reason"] = "PROVIDER_INITIALIZATION_FAILED"
            source["errors"] = [f"{type(exc).__name__}: {_compact(exc)[:300]}"]
            sources.append(source)
            continue

        source["queries_attempted"] = 1
        requests_made += 1
        try:
            hits = provider.search(query.query, count=results_per_query)
            source["queries_succeeded"] = 1
        except Exception as exc:
            source["status"] = "BLOCKED_RETRIEVAL"
            source["block_reason"] = "SEARCH_REQUEST_FAILED"
            source["errors"] = [f"{type(exc).__name__}: {_compact(exc)[:300]}"]
            sources.append(source)
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
            signal = english_bridal_signal_from_hit(
                hit,
                market_code=market_code,
                query=query,
                observed_at=now,
            )
            if signal is None:
                rejected += 1
                continue
            accepted[signal.signal_id] = signal.model_dump(mode="json")

        source["accepted_signal_count"] = len(accepted)
        source["rejected_result_count"] = rejected
        source["duplicate_result_count"] = duplicates
        source["signals"] = [accepted[key] for key in sorted(accepted)]
        source["status"] = "SUCCESS" if accepted else "VALID_ZERO"
        source["block_reason"] = None

        artifact_dir = root_path / _compact(target.get("artifact_dir"))
        report_path = artifact_dir / _compact(
            target.get("market_signal_report_file") or "market-signal-report.json"
        )
        source["stored_signal_count"] = _write_merged_market_signal_report(
            report_path,
            market_code=market_code,
            signals=source["signals"],
            observed_at=now,
        )
        source["artifact_path"] = report_path.relative_to(root_path).as_posix()
        sources.append(source)

    status_counts: dict[str, int] = {}
    for source in sources:
        status = _compact(source.get("status")).upper() or "UNKNOWN"
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso_utc(now),
        "feed_family": local_feed.FEED_FAMILY,
        "search_lane": ENGLISH_SEARCH_LANE,
        "search_language": "en",
        "retrieval_transport": "BRAVE_SEARCH",
        "market_coverage": list(SUPPORTED_MARKETS),
        "market_count": len(sources),
        "query_budget_total": len(SUPPORTED_MARKETS),
        "requests_made": requests_made,
        "results_per_query": results_per_query,
        "freshness": freshness,
        "status_counts": status_counts,
        "sources": sources,
        "signal_count": sum(
            int(source.get("accepted_signal_count") or 0) for source in sources
        ),
        "private_single_dress_listings_rejected": True,
        "source_page_verification_required": True,
        **_safety_payload(),
    }


def _source_map(report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in report.get("sources") or []:
        if not isinstance(raw, Mapping):
            continue
        market = _compact(raw.get("source_country")).upper()
        if market:
            result[market] = deepcopy(dict(raw))
    return result


def _merged_status(
    local_status: str,
    english_status: str,
    signal_count: int,
) -> str:
    successish = {"SUCCESS", "VALID_ZERO"}
    statuses = {local_status, english_status}
    if signal_count:
        return "SUCCESS" if statuses <= successish else "PARTIAL_RETRIEVAL"
    if statuses <= successish:
        return "VALID_ZERO"
    if statuses & successish:
        return "PARTIAL_RETRIEVAL"
    if statuses == {"BLOCKED_CONFIGURATION"}:
        return "BLOCKED_CONFIGURATION"
    return "BLOCKED_RETRIEVAL"


def merge_bilingual_bridal_reports(
    local_report: Mapping[str, Any],
    english_report: Mapping[str, Any],
) -> dict[str, Any]:
    """Combine both search lanes while deduplicating canonical signal identity."""
    local_sources = _source_map(local_report)
    english_sources = _source_map(english_report)
    sources: list[dict[str, Any]] = []

    for market in SUPPORTED_MARKETS:
        local = local_sources.get(market, {})
        english = english_sources.get(market, {})
        merged_signals: dict[str, dict[str, Any]] = {}
        raw_count = 0
        for source in (local, english):
            for raw in source.get("signals") or []:
                if not isinstance(raw, Mapping):
                    continue
                raw_count += 1
                signal_id = _compact(raw.get("signal_id"))
                if signal_id:
                    merged_signals[signal_id] = deepcopy(dict(raw))

        local_status = _compact(local.get("status")).upper() or "UNKNOWN"
        english_status = _compact(english.get("status")).upper() or "UNKNOWN"
        signals = [merged_signals[key] for key in sorted(merged_signals)]
        errors = [
            f"local: {item}" for item in local.get("errors") or []
        ] + [
            f"english: {item}" for item in english.get("errors") or []
        ]
        source = {
            "schema_version": SCHEMA_VERSION,
            "feed_family": local_feed.FEED_FAMILY,
            "source": "Brave Search bilingual bridal liquidation feed",
            "source_country": market,
            "search_languages": ["local-market-language", "en"],
            "search_lanes": ["LOCAL_MARKET", ENGLISH_SEARCH_LANE],
            "query_budget": int(local.get("query_budget") or 0)
            + int(english.get("query_budget") or 0),
            "queries_attempted": int(local.get("queries_attempted") or 0)
            + int(english.get("queries_attempted") or 0),
            "queries_succeeded": int(local.get("queries_succeeded") or 0)
            + int(english.get("queries_succeeded") or 0),
            "accepted_signal_count": len(signals),
            "local_signal_count": int(local.get("accepted_signal_count") or 0),
            "english_signal_count": int(english.get("accepted_signal_count") or 0),
            "cross_lane_duplicate_count": max(0, raw_count - len(signals)),
            "rejected_result_count": int(local.get("rejected_result_count") or 0)
            + int(english.get("rejected_result_count") or 0),
            "duplicate_result_count": int(local.get("duplicate_result_count") or 0)
            + int(english.get("duplicate_result_count") or 0),
            "local_language_status": local_status,
            "english_language_status": english_status,
            "signals": signals,
            "errors": errors,
            "status": _merged_status(local_status, english_status, len(signals)),
            "block_reason": None,
            "queries": [
                {
                    "query_id": local.get("query_id"),
                    "query": local.get("query"),
                    "language": "local-market-language",
                    "lane": "LOCAL_MARKET",
                },
                {
                    "query_id": english.get("query_id"),
                    "query": english.get("query"),
                    "language": "en",
                    "lane": ENGLISH_SEARCH_LANE,
                },
            ],
            **_safety_payload(),
        }
        artifact_path = english.get("artifact_path") or local.get("artifact_path")
        if artifact_path:
            source["artifact_path"] = artifact_path
        stored = english.get("stored_signal_count")
        if stored is None:
            stored = local.get("stored_signal_count")
        if stored is not None:
            source["stored_signal_count"] = stored
        sources.append(source)

    status_counts: dict[str, int] = {}
    unique_signals: set[str] = set()
    for source in sources:
        status = _compact(source.get("status")).upper() or "UNKNOWN"
        status_counts[status] = status_counts.get(status, 0) + 1
        for signal in source.get("signals") or []:
            if isinstance(signal, Mapping):
                signal_id = _compact(signal.get("signal_id"))
                if signal_id:
                    unique_signals.add(signal_id)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": english_report.get("generated_at")
        or local_report.get("generated_at"),
        "feed_family": local_feed.FEED_FAMILY,
        "retrieval_transport": "BRAVE_SEARCH",
        "market_coverage": list(SUPPORTED_MARKETS),
        "market_count": len(SUPPORTED_MARKETS),
        "search_languages": ["local-market-language", "en"],
        "english_market_search_enabled": True,
        "query_budget_total": int(local_report.get("query_budget_total") or 0)
        + int(english_report.get("query_budget_total") or 0),
        "requests_made": int(local_report.get("requests_made") or 0)
        + int(english_report.get("requests_made") or 0),
        "local_requests_made": int(local_report.get("requests_made") or 0),
        "english_requests_made": int(english_report.get("requests_made") or 0),
        "results_per_query": english_report.get("results_per_query")
        or local_report.get("results_per_query"),
        "freshness": english_report.get("freshness")
        or local_report.get("freshness"),
        "status_counts": status_counts,
        "sources": sources,
        "signal_count": len(unique_signals),
        "local_signal_count": int(local_report.get("signal_count") or 0),
        "english_signal_count": int(english_report.get("signal_count") or 0),
        "private_single_dress_listings_rejected": True,
        "source_page_verification_required": True,
        "local_language_report": deepcopy(dict(local_report)),
        "english_market_report": deepcopy(dict(english_report)),
        **_safety_payload(),
    }


def collect_manifest_bilingual_bridal_liquidation_signals(
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
    observed_at: datetime | None = None,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory = _default_provider_factory,
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
    freshness: str | None = DEFAULT_FRESHNESS,
) -> dict[str, Any]:
    """Run local and English bridal searches through the same bounded feed."""
    local_report = _ORIGINAL_LOCAL_COLLECTOR(
        manifest,
        root=root,
        observed_at=observed_at,
        environment=environment,
        provider_factory=provider_factory,
        results_per_query=results_per_query,
        freshness=freshness,
    )
    english_report = collect_manifest_english_bridal_signals(
        manifest,
        root=root,
        observed_at=observed_at,
        environment=environment,
        provider_factory=provider_factory,
        results_per_query=results_per_query,
        freshness=freshness,
    )
    return merge_bilingual_bridal_reports(local_report, english_report)


def install_bilingual_bridal_search() -> None:
    """Expose the bilingual collector through the existing bridal-feed import."""
    current = local_feed.collect_manifest_bridal_liquidation_signals
    if getattr(current, "_bilingual_bridal_search_v1", False):
        return
    collect_manifest_bilingual_bridal_liquidation_signals._bilingual_bridal_search_v1 = True  # type: ignore[attr-defined]
    local_feed.collect_manifest_bridal_liquidation_signals = (  # type: ignore[assignment]
        collect_manifest_bilingual_bridal_liquidation_signals
    )
