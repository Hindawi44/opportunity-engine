"""Bounded Italy-wide clothing liquidation discovery foundation.

This is the first Italy core-market layer. It intentionally stops at durable
market signals: public-web and official judicial-sale hits are never promoted
into opportunities, never contacted, and never used to bid, reserve, buy, or
pay. Later layers may persist entity scents, follow them across days, and route
exact lot pages into source-specific verification.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import html
import re
import unicodedata
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider
from opportunity_engine.market_intelligence import (
    MarketSignalRecord,
    MarketSignalStatus,
    MarketSignalType,
)
from opportunity_engine.unified_models import Evidence


SCHEMA_VERSION = "italy-market-discovery-1.1"
FEED_FAMILY = "ITALY_MARKET_DISCOVERY_V1"
MARKET_CODE = "IT"
DEFAULT_RESULTS_PER_QUERY = 10
MAX_RESULTS_PER_QUERY = 10
DEFAULT_FRESHNESS = "pm"


@dataclass(frozen=True, slots=True)
class ItalyDiscoveryQuery:
    query_id: str
    intent: str
    query: str
    official_only: bool = False


ITALY_DISCOVERY_QUERIES: tuple[ItalyDiscoveryQuery, ...] = (
    ItalyDiscoveryQuery(
        "it-pvp-official-clothing",
        "OFFICIAL_JUDICIAL_SALES",
        'site:pvp.giustizia.it/pvp (abbigliamento OR calzature OR moda OR tessile) '
        '(asta OR vendita OR lotto OR magazzino)',
        official_only=True,
    ),
    ItalyDiscoveryQuery(
        "it-fashion-insolvency-liquidation",
        "INSOLVENCY_LIQUIDATION",
        '("liquidazione giudiziale" OR fallimento OR insolvenza OR "procedura concorsuale") '
        '(abbigliamento OR moda OR tessile OR "negozio di abbigliamento")',
    ),
    ItalyDiscoveryQuery(
        "it-fashion-business-closure",
        "BUSINESS_CLOSURE",
        '("cessazione attività" OR "chiusura negozio" OR "svendita totale" OR '
        '"liquidazione totale") (abbigliamento OR moda OR vestiti OR calzature)',
    ),
    ItalyDiscoveryQuery(
        "it-fashion-stocklot-wholesale",
        "STOCKLOT_WHOLESALE",
        '("stock abbigliamento" OR "rimanenze di magazzino" OR "fine serie" OR '
        '"lotto abbigliamento") (vendita OR ingrosso OR liquidazione OR magazzino)',
    ),
    ItalyDiscoveryQuery(
        "it-fashion-auction-lots",
        "AUCTION_LOTS",
        '(asta OR "vendita fallimentare" OR "asta giudiziaria") '
        '("lotto abbigliamento" OR "stock moda" OR "magazzino tessile" OR calzature)',
    ),
    ItalyDiscoveryQuery(
        "it-bridal-liquidation-stock",
        "BRIDAL_LIQUIDATION",
        '("atelier sposa" OR "abiti da sposa" OR "negozio sposa" OR campionario) '
        '(liquidazione OR cessazione OR svendita OR stock OR fallimento)',
    ),
    ItalyDiscoveryQuery(
        "it-fashion-warehouse-clearance",
        "WAREHOUSE_CLEARANCE",
        '("magazzino abbigliamento" OR "stock invenduto" OR "rimanenze abbigliamento" '
        'OR "pronta consegna abbigliamento") (liquidazione OR vendita OR lotto OR stock)',
    ),
)

DEFAULT_QUERY_BUDGET = len(ITALY_DISCOVERY_QUERIES)
MAX_QUERY_BUDGET = len(ITALY_DISCOVERY_QUERIES)

_CLOTHING_TERMS = (
    "abbigliamento",
    "moda",
    "vestiti",
    "capi",
    "tessile",
    "tessili",
    "calzature",
    "scarpe",
    "negozio di abbigliamento",
    "magazzino abbigliamento",
    "stock moda",
)
_BRIDAL_TERMS = (
    "atelier sposa",
    "abiti da sposa",
    "abito da sposa",
    "abiti sposa",
    "negozio sposa",
    "campionario sposa",
)
_INSOLVENCY_TERMS = (
    "liquidazione giudiziale",
    "fallimento",
    "insolvenza",
    "procedura concorsuale",
    "curatore",
)
_CLOSURE_TERMS = (
    "cessazione attività",
    "cessazione attivita",
    "chiusura negozio",
    "svendita totale",
    "liquidazione totale",
    "chiusura attività",
    "chiusura attivita",
)
_SURPLUS_TERMS = (
    "stock abbigliamento",
    "rimanenze di magazzino",
    "rimanenze abbigliamento",
    "fine serie",
    "lotto abbigliamento",
    "stock invenduto",
    "magazzino abbigliamento",
    "pronta consegna abbigliamento",
)
_AUCTION_TERMS = (
    "asta",
    "asta giudiziaria",
    "vendita fallimentare",
    "vendita giudiziaria",
    "lotto",
)
_COMMERCIAL_ACTION_TERMS = (
    "vendita",
    "vendite",
    "vendesi",
    "vendere",
    "acquisto",
    "acquistare",
    "ingrosso",
    "all'ingrosso",
    "liquidazione",
    "svendita",
    "cessazione attività",
    "cessazione attivita",
    "asta",
    "aste",
    "lotto",
    "lotti",
    "prezzo",
    "prezzi",
    "disponibile",
    "disponibili",
    "offerta",
    "offerte",
    "outlet",
)
_COMMERCIAL_GATE_INTENTS = {"STOCKLOT_WHOLESALE", "WAREHOUSE_CLEARANCE"}
_TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}
_OFFICIAL_PVP_DOMAIN = "pvp.giustizia.it"

ProviderFactory = Callable[[str, str, str | None], SearchProvider]


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _canonical_url(raw_url: object) -> str | None:
    text = _compact(raw_url)
    if not text:
        return None
    try:
        parsed = urlsplit(text)
    except ValueError:
        return None
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        return None
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_")
        and key.casefold() not in _TRACKING_QUERY_KEYS
    ]
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit(
        ("https", parsed.netloc.casefold(), path, urlencode(filtered_query, doseq=True), "")
    )


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").casefold().rstrip(".")


def _normalise_match_text(value: object) -> str:
    decoded = html.unescape(_compact(value))
    return unicodedata.normalize("NFKC", decoded).casefold()


def _term_present(text: str, term: str) -> bool:
    normalized_text = _normalise_match_text(text)
    normalized_term = _normalise_match_text(term)
    if not normalized_term:
        return False
    pattern = rf"(?<!\w){re.escape(normalized_term)}(?!\w)"
    return re.search(pattern, normalized_text, flags=re.UNICODE) is not None


def _matched(text: str, terms: Sequence[str]) -> list[str]:
    return sorted({term for term in terms if _term_present(text, term)})


def _classify(text: str) -> tuple[MarketSignalType | None, list[str], list[str], bool]:
    clothing = _matched(text, _CLOTHING_TERMS)
    bridal = _matched(text, _BRIDAL_TERMS)
    domain_terms = sorted(set(clothing + bridal))
    if not domain_terms:
        return None, [], [], False

    categories = (
        (MarketSignalType.INSOLVENCY_OR_LIQUIDATION, _INSOLVENCY_TERMS),
        (MarketSignalType.BUSINESS_CLOSURE, _CLOSURE_TERMS),
        (MarketSignalType.WAREHOUSE_SURPLUS, _SURPLUS_TERMS),
        (MarketSignalType.AUCTION_EVENT, _AUCTION_TERMS),
    )
    for signal_type, terms in categories:
        event_terms = _matched(text, terms)
        if event_terms:
            return signal_type, domain_terms, event_terms, bool(bridal)
    return None, domain_terms, [], bool(bridal)


def italy_signal_from_hit(
    hit: SearchHit,
    *,
    query: ItalyDiscoveryQuery,
    rank: int,
    observed_at: datetime,
) -> MarketSignalRecord | None:
    """Convert one Italian search hit into an unverified durable market signal."""
    if not isinstance(hit, SearchHit):
        return None
    title = _compact(hit.title)
    description = _compact(hit.description)
    if not title:
        return None
    url = _canonical_url(hit.url)
    if not url:
        return None
    if query.official_only and _host(url) != _OFFICIAL_PVP_DOMAIN:
        return None

    combined = f"{title} {description}".strip()
    signal_type, domain_terms, event_terms, bridal = _classify(combined)
    if signal_type is None:
        return None

    # Query membership is not evidence. A Bridal search hit must itself contain
    # explicit bridal language, otherwise general fashion/insolvency results leak
    # into the bridal lane.
    if query.intent == "BRIDAL_LIQUIDATION" and not bridal:
        return None

    commercial_action_terms = _matched(combined, _COMMERCIAL_ACTION_TERMS)
    # Stock/warehouse editorial pages can mention inventory without offering any
    # commercial action. Keep those out of durable opportunity scent storage.
    if query.intent in _COMMERCIAL_GATE_INTENTS and not commercial_action_terms:
        return None

    official = _host(url) == _OFFICIAL_PVP_DOMAIN
    confidence = 0.58
    if official:
        confidence += 0.09
    if _matched(title, domain_terms):
        confidence += 0.04
    if _matched(title, event_terms):
        confidence += 0.04
    if len(event_terms) > 1:
        confidence += 0.03

    signal_id = "italy-discovery:" + sha256(url.encode("utf-8")).hexdigest()[:24]
    evidence = Evidence(
        evidence_type="OFFICIAL_PUBLIC_SALE_SEARCH_RESULT" if official else "BRAVE_SEARCH_RESULT",
        value=combined[:4000],
        source_url=url,
        captured_at=observed_at,
        verified=False,
        metadata={
            "feed_family": FEED_FAMILY,
            "query_id": query.query_id,
            "intent": query.intent,
            "source_rank": rank,
            "provider": _compact(hit.provider) or "Brave Search",
            "verification_status": "UNVERIFIED_PUBLIC_WEB_SEARCH_HIT",
            "official_source_domain": official,
        },
    )
    return MarketSignalRecord(
        signal_id=signal_id,
        signal_type=signal_type,
        value=(description or title)[:500],
        source="Italy market discovery radar",
        observed_at=observed_at,
        confidence=min(0.78, confidence),
        source_country=MARKET_CODE,
        source_url=url,
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
            "market_role": "CORE_OPPORTUNITY_DISCOVERY_CANDIDATE",
            "inventory_domain": "BRIDAL" if bridal else "CLOTHING_FASHION",
            "query_id": query.query_id,
            "intent": query.intent,
            "query": query.query,
            "source_rank": rank,
            "domain_terms": domain_terms,
            "event_terms": event_terms,
            "commercial_action_terms": commercial_action_terms,
            "canonical_url": url,
            "source_scope": "OFFICIAL_JUDICIAL_SALES" if official else "PUBLIC_WEB_DISCOVERY",
            "source_page_verification_required": True,
            "promotion_to_opportunity_allowed": False,
            "analysis_eligible": False,
            "top5_eligible": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_reservation": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        },
    )


def _default_provider_factory(
    market_code: str,
    api_key: str,
    freshness: str | None,
) -> SearchProvider:
    return BraveSearchProvider(
        api_key,
        freshness=freshness,
        extra_snippets=True,
        operators=True,
        country=market_code,
    )


def collect_italy_market_signals(
    *,
    observed_at: datetime | None = None,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory = _default_provider_factory,
    query_budget: int = DEFAULT_QUERY_BUDGET,
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
    freshness: str | None = DEFAULT_FRESHNESS,
) -> dict[str, Any]:
    """Run the bounded national Italy query pack without altering the daily workflow."""
    if not 1 <= query_budget <= MAX_QUERY_BUDGET:
        raise ValueError(f"query_budget must be between 1 and {MAX_QUERY_BUDGET}")
    if not 1 <= results_per_query <= MAX_RESULTS_PER_QUERY:
        raise ValueError(
            f"results_per_query must be between 1 and {MAX_RESULTS_PER_QUERY}"
        )

    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    env = environment or {}
    api_key = _compact(env.get("BRAVE_SEARCH_API_KEY")) or _compact(env.get("BRAVE_API_KEY"))

    base = {
        "schema_version": SCHEMA_VERSION,
        "feed_family": FEED_FAMILY,
        "generated_at": now.isoformat(),
        "source_country": MARKET_CODE,
        "market_role": "CORE_OPPORTUNITY_DISCOVERY_CANDIDATE",
        "query_budget": query_budget,
        "results_per_query": results_per_query,
        "freshness": freshness,
        "queries_attempted": 0,
        "queries_succeeded": 0,
        "accepted_signal_count": 0,
        "rejected_result_count": 0,
        "duplicate_result_count": 0,
        "independent_domain_count": 0,
        "signals": [],
        "errors": [],
        "source_page_verification_required": True,
        "promotion_to_opportunity_allowed": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    if not api_key:
        return {
            **base,
            "status": "BLOCKED_CONFIGURATION",
            "block_reason": "BRAVE_SEARCH_API_KEY_MISSING",
        }

    try:
        provider = provider_factory(MARKET_CODE, api_key, freshness)
    except Exception as exc:
        return {
            **base,
            "status": "BLOCKED_RETRIEVAL",
            "block_reason": "PROVIDER_INITIALIZATION_FAILED",
            "errors": [f"{type(exc).__name__}: {_compact(exc)[:300]}"],
        }

    accepted: dict[str, dict[str, Any]] = {}
    seen_urls: set[str] = set()
    errors: list[str] = []
    rejected = duplicates = succeeded = 0
    query_stats: list[dict[str, Any]] = []

    for query in ITALY_DISCOVERY_QUERIES[:query_budget]:
        query_accepted = query_rejected = query_duplicates = 0
        try:
            hits = provider.search(query.query, count=results_per_query)
            succeeded += 1
            query_status = "SUCCESS"
        except Exception as exc:
            errors.append(f"{query.query_id}: {type(exc).__name__}: {_compact(exc)[:300]}")
            query_stats.append(
                {
                    "query_id": query.query_id,
                    "intent": query.intent,
                    "official_only": query.official_only,
                    "status": "FAILED",
                    "accepted": 0,
                    "rejected": 0,
                    "duplicates": 0,
                }
            )
            continue

        for rank, hit in enumerate(hits, start=1):
            if not isinstance(hit, SearchHit):
                rejected += 1
                query_rejected += 1
                continue
            url = _canonical_url(hit.url)
            if not url:
                rejected += 1
                query_rejected += 1
                continue
            if url in seen_urls:
                duplicates += 1
                query_duplicates += 1
                continue
            seen_urls.add(url)
            signal = italy_signal_from_hit(hit, query=query, rank=rank, observed_at=now)
            if signal is None:
                rejected += 1
                query_rejected += 1
                continue
            accepted[signal.signal_id] = signal.model_dump(mode="json")
            query_accepted += 1

        query_stats.append(
            {
                "query_id": query.query_id,
                "intent": query.intent,
                "official_only": query.official_only,
                "status": query_status,
                "accepted": query_accepted,
                "rejected": query_rejected,
                "duplicates": query_duplicates,
            }
        )

    signals = [accepted[key] for key in sorted(accepted)]
    domains = {
        _host(_compact(signal.get("source_url")))
        for signal in signals
        if _compact(signal.get("source_url"))
    }
    intent_counts = Counter(
        _compact((signal.get("metadata") or {}).get("intent"))
        for signal in signals
        if isinstance(signal.get("metadata"), Mapping)
    )
    status = "SUCCESS" if signals else (
        "PARTIAL_RETRIEVAL"
        if errors and succeeded
        else ("BLOCKED_RETRIEVAL" if errors else "VALID_ZERO")
    )
    return {
        **base,
        "status": status,
        "block_reason": None,
        "queries_attempted": query_budget,
        "queries_succeeded": succeeded,
        "accepted_signal_count": len(signals),
        "rejected_result_count": rejected,
        "duplicate_result_count": duplicates,
        "independent_domain_count": len(domains),
        "intent_counts": dict(sorted(intent_counts.items())),
        "query_stats": query_stats,
        "signals": signals,
        "errors": errors,
        "official_pvp_enabled": True,
        "official_pvp_domain": _OFFICIAL_PVP_DOMAIN,
    }
