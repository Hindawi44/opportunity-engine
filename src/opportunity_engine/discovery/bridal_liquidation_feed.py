"""Bounded bridal-liquidation market-signal feed for Norway, Sweden, and Germany.

The feed is a niche tributary into the existing market-intelligence river. It
searches Brave for commercial bridal-store liquidation, insolvency, stock-clearance,
and batch-sale signals. A private person selling one used wedding dress is rejected.
Accepted links remain unverified market signals and can never be promoted directly
into an opportunity or trigger contact, bidding, purchasing, reservation, or payment.

Sweden and Germany use a bounded intent pack. One core query always runs; adaptive
queries run only while the result set is weak (fewer than two accepted signals or
fewer than two independent domains). This increases depth without turning the feed
into an unbounded crawler.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit

from opportunity_engine.discovery.brave_market_signal_radar import (
    _canonical_url,
    _compact,
    _default_provider_factory,
    _iso_utc,
    _target_spec,
    _write_merged_market_signal_report,
)
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider
from opportunity_engine.market_intelligence import (
    MarketSignalRecord,
    MarketSignalStatus,
    MarketSignalType,
)
from opportunity_engine.unified_models import Evidence


SCHEMA_VERSION = "bridal-liquidation-feed-1.1"
FEED_FAMILY = "BRIDAL_LIQUIDATION_FEED_V1"
SUPPORTED_MARKETS = ("NO", "SE", "DE")
DEFAULT_RESULTS_PER_QUERY = 8
MAX_RESULTS_PER_QUERY = 10
DEFAULT_FRESHNESS = "py"
ADAPTIVE_MARKETS = frozenset({"SE", "DE"})
ADAPTIVE_MIN_SIGNAL_COUNT = 2
ADAPTIVE_MIN_DISTINCT_DOMAINS = 2


@dataclass(frozen=True, slots=True)
class BridalQuery:
    query_id: str
    query: str
    intent: str = "LIQUIDATION"
    phase: str = "CORE"


BRIDAL_QUERIES: dict[str, BridalQuery] = {
    "NO": BridalQuery(
        "no-bridal-liquidation",
        '(brudesalong OR brudebutikk OR brudekjoler OR prøvekjoler) '
        '(opphørssalg OR konkurs OR avvikling OR lagertømming OR "varelager selges")',
    ),
    "SE": BridalQuery(
        "se-bridal-liquidation",
        '(brudbutik OR bröllopsbutik OR brudklänningar OR provklänningar) '
        '(utförsäljning OR konkurs OR avveckling OR lagerrensning OR "lager säljes")',
    ),
    "DE": BridalQuery(
        "de-bridal-liquidation",
        '(Brautmodengeschäft OR Brautladen OR Brautkleider OR Musterkleider) '
        '(Geschäftsauflösung OR Insolvenz OR Räumungsverkauf OR Restposten OR Lagerverkauf)',
    ),
}

# Preserve the original BRIDAL_QUERIES public contract while giving the two weak
# large markets several distinct commercial intents. Adaptive rows are attempted
# only while the core result remains shallow.
BRIDAL_QUERY_PACKS: dict[str, tuple[BridalQuery, ...]] = {
    "NO": (BRIDAL_QUERIES["NO"],),
    "SE": (
        BRIDAL_QUERIES["SE"],
        BridalQuery(
            "se-bridal-sample-stock",
            '(brudklänningar OR provklänningar OR butiksexemplar) '
            '("lagerförsäljning" OR utförsäljning OR lagerrensning OR "butiksexemplar säljes")',
            intent="SAMPLE_STOCK",
            phase="ADAPTIVE",
        ),
        BridalQuery(
            "se-bridal-stocklot",
            '(brudklänningar OR brudbutik OR bröllopsbutik) '
            '(varulager OR restlager OR lagerparti OR parti OR grossist) '
            '(säljes OR försäljning OR avveckling)',
            intent="STOCKLOT_WHOLESALE",
            phase="ADAPTIVE",
        ),
        BridalQuery(
            "se-bridal-auction",
            '(brudklänningar OR brudbutik OR provklänningar) '
            '(auktion OR konkursauktion OR "exekutiv försäljning")',
            intent="AUCTION",
            phase="ADAPTIVE",
        ),
        BridalQuery(
            "se-bridal-closure-stock",
            '(brudbutik OR bröllopsbutik) '
            '(butiksstängning OR butiksnedläggning OR konkurs OR likvidation) '
            '(lager OR varulager OR brudklänningar)',
            intent="CLOSURE_STOCK",
            phase="ADAPTIVE",
        ),
    ),
    "DE": (
        BRIDAL_QUERIES["DE"],
        BridalQuery(
            "de-bridal-sample-stock",
            '(Brautkleider OR Musterkleider OR Ausstellungsstücke) '
            '(Musterverkauf OR Abverkauf OR Räumungsverkauf OR Lagerverkauf)',
            intent="SAMPLE_STOCK",
            phase="ADAPTIVE",
        ),
        BridalQuery(
            "de-bridal-stocklot",
            '(Brautkleider OR Brautmode OR Musterkleider) '
            '(Restposten OR Warenbestand OR Warenposten OR Sonderposten OR Posten) '
            '(Großhandel OR Verkauf OR Verwertung)',
            intent="STOCKLOT_WHOLESALE",
            phase="ADAPTIVE",
        ),
        BridalQuery(
            "de-bridal-auction",
            '(Brautkleider OR Brautladen OR Brautmode) '
            '(Auktion OR Versteigerung OR Insolvenzauktion OR Insolvenzversteigerung)',
            intent="AUCTION",
            phase="ADAPTIVE",
        ),
        BridalQuery(
            "de-bridal-closure-stock",
            '(Brautladen OR Brautmodengeschäft) '
            '(Geschäftsaufgabe OR Geschäftsauflösung OR Insolvenz OR Ladenschließung) '
            '(Warenbestand OR Lager OR Musterkleider)',
            intent="CLOSURE_STOCK",
            phase="ADAPTIVE",
        ),
    ),
}

_BRIDAL_TERMS: dict[str, tuple[str, ...]] = {
    "NO": (
        "brudesalong",
        "brudebutikk",
        "brudekjole",
        "brudekjoler",
        "prøvekjole",
        "prøvekjoler",
        "brudekolleksjon",
    ),
    "SE": (
        "brudbutik",
        "bröllopsbutik",
        "brollopsbutik",
        "brudklänning",
        "brudklänningar",
        "brudklanning",
        "brudklanningar",
        "provklänning",
        "provklänningar",
        "provklanning",
        "provklanningar",
        "butiksexemplar",
    ),
    "DE": (
        "brautmodengeschäft",
        "brautmodengeschaft",
        "brautladen",
        "brautmode",
        "brautkleid",
        "brautkleider",
        "musterkleid",
        "musterkleider",
        "brautkollektion",
        "ausstellungsstücke",
        "ausstellungsstucke",
    ),
}

_COMMERCIAL_BATCH_TERMS: dict[str, tuple[str, ...]] = {
    "NO": (
        "brudesalong",
        "brudebutikk",
        "brudekjoler",
        "prøvekjoler",
        "brudekolleksjon",
        "varelager",
        "restlager",
        "parti",
        "lager",
    ),
    "SE": (
        "brudbutik",
        "bröllopsbutik",
        "brollopsbutik",
        "brudklänningar",
        "brudklanningar",
        "provklänningar",
        "provklanningar",
        "butiksexemplar",
        "lager",
        "varulager",
        "restlager",
        "lagerparti",
        "parti",
        "kollektion",
        "grossist",
    ),
    "DE": (
        "brautmodengeschäft",
        "brautmodengeschaft",
        "brautladen",
        "brautmode",
        "brautkleider",
        "musterkleider",
        "ausstellungsstücke",
        "ausstellungsstucke",
        "lager",
        "warenbestand",
        "restposten",
        "sonderposten",
        "warenposten",
        "posten",
        "kollektion",
        "großhandel",
        "grosshandel",
    ),
}

_INSOLVENCY_TERMS: dict[str, tuple[str, ...]] = {
    "NO": ("konkurs", "insolvens", "tvangsavvikling", "likvidasjon"),
    "SE": ("konkurs", "insolvens", "likvidation", "rekonstruktion"),
    "DE": (
        "insolvenz",
        "insolvenzverfahren",
        "insolvenzauktion",
        "insolvenzversteigerung",
        "liquidation",
        "konkurs",
    ),
}
_CLOSURE_TERMS: dict[str, tuple[str, ...]] = {
    "NO": ("opphørssalg", "avvikling", "nedleggelse"),
    "SE": (
        "utförsäljning",
        "utforsaljning",
        "avveckling",
        "butiksstängning",
        "butiksnedläggning",
    ),
    "DE": (
        "geschäftsauflösung",
        "geschaftsauflosung",
        "geschäftsaufgabe",
        "geschaftsaufgabe",
        "geschäftsschließung",
        "geschaftsschliessung",
        "ladenschließung",
        "ladenschliessung",
        "räumungsverkauf",
        "raumungsverkauf",
        "ladenauflösung",
        "ladenauflosung",
    ),
}
_SURPLUS_TERMS: dict[str, tuple[str, ...]] = {
    "NO": (
        "lagertømming",
        "lager tømmes",
        "varelager selges",
        "restlager",
        "prøvekjoler",
    ),
    "SE": (
        "lagerrensning",
        "lager säljes",
        "lager saljes",
        "lagerförsäljning",
        "lagerforsaljning",
        "restlager",
        "lagerparti",
        "provklänningar",
        "provklanningar",
        "butiksexemplar",
    ),
    "DE": (
        "lagerverkauf",
        "restposten",
        "warenbestand",
        "warenposten",
        "sonderposten",
        "abverkauf",
        "musterverkauf",
        "musterkleider",
        "ausstellungsstücke",
        "ausstellungsstucke",
        "verwertung",
    ),
}
_AUCTION_TERMS: dict[str, tuple[str, ...]] = {
    "NO": ("auksjon", "tvangssalg"),
    "SE": (
        "auktion",
        "konkursauktion",
        "exekutiv försäljning",
        "exekutiv forsaljning",
    ),
    "DE": (
        "auktion",
        "versteigerung",
        "insolvenzauktion",
        "insolvenzversteigerung",
        "zwangsversteigerung",
    ),
}

ProviderFactory = Callable[[str, str, str | None], SearchProvider]


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


def _classify_event(
    market_code: str,
    text: str,
) -> tuple[MarketSignalType | None, list[str]]:
    categories = (
        (MarketSignalType.INSOLVENCY_OR_LIQUIDATION, _INSOLVENCY_TERMS[market_code]),
        (MarketSignalType.BUSINESS_CLOSURE, _CLOSURE_TERMS[market_code]),
        (MarketSignalType.WAREHOUSE_SURPLUS, _SURPLUS_TERMS[market_code]),
        (MarketSignalType.AUCTION_EVENT, _AUCTION_TERMS[market_code]),
    )
    for signal_type, terms in categories:
        matched = _matched_terms(text, terms)
        if matched:
            return signal_type, matched
    return None, []


def bridal_signal_from_hit(
    hit: SearchHit,
    *,
    market_code: str,
    query: BridalQuery,
    observed_at: datetime,
) -> MarketSignalRecord | None:
    """Accept only commercial bridal inventory events, never a lone private dress."""
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

    bridal_terms = _matched_terms(combined, _BRIDAL_TERMS[market])
    batch_terms = _matched_terms(combined, _COMMERCIAL_BATCH_TERMS[market])
    signal_type, event_terms = _classify_event(market, combined)
    if not bridal_terms or not batch_terms or signal_type is None:
        return None

    canonical_url = _canonical_url(_compact(hit.url))
    digest = sha256(canonical_url.encode("utf-8")).hexdigest()[:24]
    signal_id = f"bridal-feed:{market.casefold()}:{digest}"
    evidence = Evidence(
        evidence_type="BRAVE_SEARCH_RESULT",
        value=combined[:4000],
        source_url=canonical_url,
        captured_at=None,
        verified=False,
        metadata={
            "feed_family": FEED_FAMILY,
            "query_id": query.query_id,
            "query_intent": query.intent,
            "query_phase": query.phase,
            "provider": _compact(hit.provider) or "Brave Search",
            "verification_status": "UNVERIFIED_PUBLIC_WEB",
        },
    )
    confidence = 0.62
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
        confidence=min(0.75, confidence),
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
            "feed_family": FEED_FAMILY,
            "inventory_domain": "BRIDAL",
            "commercial_batch_gate": True,
            "discovery_transport": "BRAVE_SEARCH",
            "verification_status": "UNVERIFIED_PUBLIC_WEB",
            "query_id": query.query_id,
            "query_intent": query.intent,
            "query_phase": query.phase,
            "bridal_terms": sorted(set(bridal_terms)),
            "commercial_batch_terms": sorted(set(batch_terms)),
            "event_terms": sorted(set(event_terms)),
            "canonical_url": canonical_url,
            **_safety_payload(),
        },
    )


def _distinct_signal_domains(signals: Mapping[str, Mapping[str, Any]]) -> int:
    domains: set[str] = set()
    for signal in signals.values():
        raw = _compact(signal.get("source_url"))
        if not raw:
            continue
        host = (urlsplit(raw).hostname or "").casefold()
        if host.startswith("www."):
            host = host[4:]
        if host:
            domains.add(host)
    return len(domains)


def _needs_adaptive(signals: Mapping[str, Mapping[str, Any]]) -> bool:
    return (
        len(signals) < ADAPTIVE_MIN_SIGNAL_COUNT
        or _distinct_signal_domains(signals) < ADAPTIVE_MIN_DISTINCT_DOMAINS
    )


def collect_manifest_bridal_liquidation_signals(
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
    observed_at: datetime | None = None,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory = _default_provider_factory,
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
    freshness: str | None = DEFAULT_FRESHNESS,
) -> dict[str, Any]:
    """Run bounded local bridal discovery with adaptive SE/DE depth."""
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
        primary_query = BRIDAL_QUERIES[market_code]
        query_pack = BRIDAL_QUERY_PACKS[market_code]
        source: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "feed_family": FEED_FAMILY,
            "source": "Brave Search bridal liquidation feed",
            "source_country": market_code,
            "freshness": freshness,
            "query_id": primary_query.query_id,
            "query": primary_query.query,
            "query_budget": len(query_pack),
            "query_plan": [
                {
                    "query_id": item.query_id,
                    "query": item.query,
                    "intent": item.intent,
                    "phase": item.phase,
                }
                for item in query_pack
            ],
            "query_runs": [],
            "results_per_query": results_per_query,
            "queries_attempted": 0,
            "queries_succeeded": 0,
            "accepted_signal_count": 0,
            "rejected_result_count": 0,
            "duplicate_result_count": 0,
            "distinct_domain_count": 0,
            "adaptive_expansion_eligible": market_code in ADAPTIVE_MARKETS,
            "adaptive_expansion_triggered": False,
            "adaptive_stop_reason": (
                "NOT_CONFIGURED" if market_code not in ADAPTIVE_MARKETS else None
            ),
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

        accepted: dict[str, dict[str, Any]] = {}
        seen_urls: set[str] = set()
        rejected = 0
        duplicates = 0

        for query in query_pack:
            if query.phase == "ADAPTIVE":
                if market_code not in ADAPTIVE_MARKETS:
                    break
                if not _needs_adaptive(accepted):
                    source["adaptive_stop_reason"] = "CORE_OR_PRIOR_EVIDENCE_SUFFICIENT"
                    break
                source["adaptive_expansion_triggered"] = True

            source["queries_attempted"] += 1
            requests_made += 1
            query_run: dict[str, Any] = {
                "query_id": query.query_id,
                "query": query.query,
                "intent": query.intent,
                "phase": query.phase,
                "status": "PLANNED",
                "returned_result_count": 0,
                "accepted_signal_count": 0,
                "rejected_result_count": 0,
                "duplicate_result_count": 0,
            }
            try:
                hits = provider.search(query.query, count=results_per_query)
                source["queries_succeeded"] += 1
                query_run["status"] = "SUCCESS"
                query_run["returned_result_count"] = len(hits)
            except Exception as exc:
                message = f"{type(exc).__name__}: {_compact(exc)[:300]}"
                source["errors"].append(f"{query.query_id}: {message}")
                query_run["status"] = "FAILED"
                query_run["error"] = message
                source["query_runs"].append(query_run)
                continue

            accepted_before = len(accepted)
            query_rejected = 0
            query_duplicates = 0
            for hit in hits:
                if not isinstance(hit, SearchHit):
                    rejected += 1
                    query_rejected += 1
                    continue
                try:
                    canonical_url = _canonical_url(_compact(hit.url))
                except ValueError:
                    rejected += 1
                    query_rejected += 1
                    continue
                if canonical_url in seen_urls:
                    duplicates += 1
                    query_duplicates += 1
                    continue
                seen_urls.add(canonical_url)
                signal = bridal_signal_from_hit(
                    hit,
                    market_code=market_code,
                    query=query,
                    observed_at=now,
                )
                if signal is None:
                    rejected += 1
                    query_rejected += 1
                    continue
                accepted.setdefault(signal.signal_id, signal.model_dump(mode="json"))

            query_run["accepted_signal_count"] = len(accepted) - accepted_before
            query_run["rejected_result_count"] = query_rejected
            query_run["duplicate_result_count"] = query_duplicates
            source["query_runs"].append(query_run)

            if query.phase == "ADAPTIVE" and not _needs_adaptive(accepted):
                source["adaptive_stop_reason"] = "EVIDENCE_DIVERSIFIED"
                break

        if market_code in ADAPTIVE_MARKETS and source["adaptive_stop_reason"] is None:
            if source["adaptive_expansion_triggered"]:
                source["adaptive_stop_reason"] = "QUERY_PACK_EXHAUSTED"
            else:
                source["adaptive_stop_reason"] = "CORE_EVIDENCE_SUFFICIENT"

        source["accepted_signal_count"] = len(accepted)
        source["rejected_result_count"] = rejected
        source["duplicate_result_count"] = duplicates
        source["distinct_domain_count"] = _distinct_signal_domains(accepted)
        source["signals"] = [accepted[key] for key in sorted(accepted)]

        if source["queries_succeeded"] == 0 and source["errors"]:
            source["status"] = "BLOCKED_RETRIEVAL"
            source["block_reason"] = "ALL_SEARCH_REQUESTS_FAILED"
        elif accepted and source["errors"]:
            source["status"] = "PARTIAL_RETRIEVAL"
            source["block_reason"] = None
        elif accepted:
            source["status"] = "SUCCESS"
            source["block_reason"] = None
        elif source["errors"]:
            source["status"] = "PARTIAL_RETRIEVAL"
            source["block_reason"] = None
        else:
            source["status"] = "VALID_ZERO"
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

    query_budget_total = sum(len(BRIDAL_QUERY_PACKS[market]) for market in SUPPORTED_MARKETS)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso_utc(now),
        "feed_family": FEED_FAMILY,
        "retrieval_transport": "BRAVE_SEARCH",
        "market_coverage": list(SUPPORTED_MARKETS),
        "market_count": len(sources),
        "query_budget_total": query_budget_total,
        "requests_made": requests_made,
        "results_per_query": results_per_query,
        "freshness": freshness,
        "adaptive_markets": sorted(ADAPTIVE_MARKETS),
        "adaptive_min_signal_count": ADAPTIVE_MIN_SIGNAL_COUNT,
        "adaptive_min_distinct_domains": ADAPTIVE_MIN_DISTINCT_DOMAINS,
        "status_counts": status_counts,
        "sources": sources,
        "signal_count": sum(
            int(source.get("accepted_signal_count") or 0) for source in sources
        ),
        "private_single_dress_listings_rejected": True,
        "source_page_verification_required": True,
        **_safety_payload(),
    }
