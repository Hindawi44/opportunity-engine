"""Bounded France-wide clothing liquidation discovery foundation.

France is opened as an official expansion market while the legacy canonical
NO/SE/DE Top-5 contract stays unchanged for backward compatibility. This layer
emits signal-only public-web evidence. Durable company memory and Follow-Up are
handled by the existing SIGNAL_FOLLOW_UP_ENGINE_V1 through the France adapter.
"""
from __future__ import annotations

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


SCHEMA_VERSION = "france-market-discovery-1.0"
FEED_FAMILY = "FRANCE_MARKET_DISCOVERY_V1"
MARKET_CODE = "FR"
DEFAULT_RESULTS_PER_QUERY = 10
MAX_RESULTS_PER_QUERY = 10
DEFAULT_FRESHNESS = "pm"


@dataclass(frozen=True, slots=True)
class FranceDiscoveryQuery:
    query_id: str
    intent: str
    query: str
    required_domains: tuple[str, ...] = ()


FRANCE_DISCOVERY_QUERIES: tuple[FranceDiscoveryQuery, ...] = (
    FranceDiscoveryQuery(
        "fr-bodacc-fashion-liquidation",
        "OFFICIAL_INSOLVENCY",
        'site:bodacc.fr ("liquidation judiciaire" OR "redressement judiciaire") '
        '(vêtements OR "prêt-à-porter" OR textile OR habillement OR chaussures OR mode)',
        required_domains=("bodacc.fr", "www.bodacc.fr"),
    ),
    FranceDiscoveryQuery(
        "fr-interencheres-judicial-fashion-stock",
        "JUDICIAL_AUCTION_STOCK",
        'site:interencheres.com ("liquidation judiciaire" OR "vente judiciaire" OR "lot judiciaire") '
        '(stock OR lot OR palettes) (vêtements OR "prêt-à-porter" OR textile OR chaussures)',
    ),
    FranceDiscoveryQuery(
        "fr-fashion-insolvency-liquidation",
        "INSOLVENCY_LIQUIDATION",
        '("liquidation judiciaire" OR "redressement judiciaire" OR "procédure collective" '
        'OR "cessation des paiements" OR "mandataire judiciaire") '
        '(vêtements OR "prêt-à-porter" OR textile OR habillement OR chaussures OR mode) '
        '(stock OR vente OR enchères OR liquidation)',
    ),
    FranceDiscoveryQuery(
        "fr-fashion-business-closure",
        "BUSINESS_CLOSURE",
        '("cessation d’activité" OR "cessation d\'activité" OR "fermeture définitive" '
        'OR "fin d’activité" OR "fin d\'activité" OR "liquidation totale") '
        '(boutique OR magasin) (vêtements OR mode OR chaussures OR mariage)',
    ),
    FranceDiscoveryQuery(
        "fr-fashion-stocklot-wholesale",
        "STOCKLOT_WHOLESALE",
        '("stock de vêtements" OR "lot de vêtements" OR "lots de vêtements" '
        'OR "stock marchandises" OR "stock magasin") '
        '(déstockage OR destockage OR "à vendre" OR vente OR grossiste OR prix)',
    ),
    FranceDiscoveryQuery(
        "fr-fashion-auction-lots",
        "AUCTION_LOTS",
        '("vente aux enchères" OR enchères OR "vente judiciaire" OR adjudication) '
        '(vêtements OR "prêt-à-porter" OR textile OR chaussures) '
        '(lot OR lots OR stock OR palettes)',
    ),
    FranceDiscoveryQuery(
        "fr-bridal-liquidation-stock",
        "BRIDAL_LIQUIDATION",
        '("robe de mariée" OR "robes de mariée" OR "boutique de mariage" OR mariée OR mariage) '
        '("liquidation judiciaire" OR fermeture OR déstockage OR stock OR enchères)',
    ),
    FranceDiscoveryQuery(
        "fr-fashion-warehouse-clearance",
        "WAREHOUSE_CLEARANCE",
        '("stock magasin" OR "stock entrepôt" OR "stock de vêtements" OR "stock textile") '
        '(déstockage OR destockage OR liquidation OR vente OR enchères OR lot)',
    ),
)

DEFAULT_QUERY_BUDGET = len(FRANCE_DISCOVERY_QUERIES)
MAX_QUERY_BUDGET = len(FRANCE_DISCOVERY_QUERIES)

_CLOTHING_TERMS = (
    "vêtement", "vêtements", "pret-a-porter", "prêt-à-porter", "textile",
    "habillement", "mode", "chaussure", "chaussures", "lingerie", "friperie",
)
_BRIDAL_TERMS = (
    "robe de mariée", "robes de mariée", "mariée", "boutique de mariage",
    "robe de mariage", "robes de mariage",
)
_INSOLVENCY_TERMS = (
    "liquidation judiciaire", "redressement judiciaire", "procédure collective",
    "procedure collective", "cessation des paiements", "mandataire judiciaire",
)
_CLOSURE_TERMS = (
    "cessation d’activité", "cessation d'activité", "fermeture définitive",
    "fermeture definitive", "fin d’activité", "fin d'activité", "liquidation totale",
)
_SURPLUS_TERMS = (
    "stock de vêtements", "stock de vetements", "stock marchandises", "stock magasin",
    "stock entrepôt", "stock entrepot", "stock textile", "lot de vêtements",
    "lot de vetements", "lots de vêtements", "lots de vetements", "déstockage", "destockage",
)
_AUCTION_TERMS = (
    "vente aux enchères", "vente aux encheres", "enchères", "encheres",
    "vente judiciaire", "lot judiciaire", "adjudication",
)
_COMMERCIAL_ACTION_TERMS = (
    "à vendre", "a vendre", "vente", "enchères", "encheres", "lot", "lots",
    "prix", "estimation", "déstockage", "destockage", "stock entier", "palettes",
)
_INVENTORY_OFFER_TERMS = (
    "à vendre", "a vendre", "vente", "enchères", "encheres", "lot", "lots",
    "prix", "estimation", "stock entier", "pièces", "pieces", "palettes",
)
_COMMERCIAL_GATE_INTENTS = {"STOCKLOT_WHOLESALE", "WAREHOUSE_CLEARANCE"}
_TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}
_OFFICIAL_DOMAINS = {"bodacc.fr", "www.bodacc.fr"}

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
        if not key.casefold().startswith("utm_") and key.casefold() not in _TRACKING_QUERY_KEYS
    ]
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit(("https", parsed.netloc.casefold(), path, urlencode(filtered_query, doseq=True), ""))


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
    return re.search(rf"(?<!\w){re.escape(normalized_term)}(?!\w)", normalized_text, flags=re.UNICODE) is not None


def _matched(text: str, terms: Sequence[str]) -> list[str]:
    return sorted({term for term in terms if _term_present(text, term)})


def _classify(text: str) -> tuple[MarketSignalType | None, list[str], list[str], bool]:
    clothing = _matched(text, _CLOTHING_TERMS)
    bridal = _matched(text, _BRIDAL_TERMS)
    domain_terms = sorted(set(clothing + bridal))
    if not domain_terms:
        return None, [], [], False
    for signal_type, terms in (
        (MarketSignalType.INSOLVENCY_OR_LIQUIDATION, _INSOLVENCY_TERMS),
        (MarketSignalType.BUSINESS_CLOSURE, _CLOSURE_TERMS),
        (MarketSignalType.WAREHOUSE_SURPLUS, _SURPLUS_TERMS),
        (MarketSignalType.AUCTION_EVENT, _AUCTION_TERMS),
    ):
        event_terms = _matched(text, terms)
        if event_terms:
            return signal_type, domain_terms, event_terms, bool(bridal)
    return None, domain_terms, [], bool(bridal)


def france_signal_from_hit(
    hit: SearchHit,
    *,
    query: FranceDiscoveryQuery,
    rank: int,
    observed_at: datetime,
) -> MarketSignalRecord | None:
    if not isinstance(hit, SearchHit):
        return None
    title = _compact(hit.title)
    description = _compact(hit.description)
    if not title:
        return None
    url = _canonical_url(hit.url)
    if not url:
        return None
    host = _host(url)
    if query.required_domains and host not in query.required_domains:
        return None

    combined = f"{title} {description}".strip()
    signal_type, domain_terms, event_terms, bridal = _classify(combined)
    if signal_type is None:
        return None
    if query.intent == "BRIDAL_LIQUIDATION" and not bridal:
        return None

    commercial_action_terms = _matched(combined, _COMMERCIAL_ACTION_TERMS)
    inventory_offer_terms = _matched(combined, _INVENTORY_OFFER_TERMS)
    if query.intent in _COMMERCIAL_GATE_INTENTS and (
        not commercial_action_terms or not inventory_offer_terms
    ):
        return None

    official = host in _OFFICIAL_DOMAINS
    confidence = 0.58 + (0.12 if official else 0.0)
    if _matched(title, domain_terms):
        confidence += 0.04
    if _matched(title, event_terms):
        confidence += 0.04
    if len(event_terms) > 1:
        confidence += 0.03

    signal_id = "france-discovery:" + sha256(url.encode("utf-8")).hexdigest()[:24]
    evidence = Evidence(
        evidence_type="OFFICIAL_PUBLIC_SEARCH_RESULT" if official else "BRAVE_SEARCH_RESULT",
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
        source="France market discovery radar",
        observed_at=observed_at,
        confidence=min(0.82, confidence),
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
            "market_role": "OFFICIAL_EXPANSION_MARKET",
            "inventory_domain": "BRIDAL" if bridal else "CLOTHING_FASHION",
            "query_id": query.query_id,
            "intent": query.intent,
            "query": query.query,
            "source_rank": rank,
            "domain_terms": domain_terms,
            "event_terms": event_terms,
            "commercial_action_terms": commercial_action_terms,
            "inventory_offer_terms": inventory_offer_terms,
            "canonical_url": url,
            "source_scope": "OFFICIAL_PUBLIC_SOURCE" if official else "PUBLIC_WEB_DISCOVERY",
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


def _default_provider_factory(market_code: str, api_key: str, freshness: str | None) -> SearchProvider:
    return BraveSearchProvider(
        api_key,
        freshness=freshness,
        extra_snippets=True,
        operators=True,
        country=market_code,
    )


def collect_france_market_signals(
    *,
    observed_at: datetime | None = None,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory = _default_provider_factory,
    query_budget: int = DEFAULT_QUERY_BUDGET,
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
    freshness: str | None = DEFAULT_FRESHNESS,
) -> dict[str, Any]:
    if not 1 <= query_budget <= MAX_QUERY_BUDGET:
        raise ValueError(f"query_budget must be between 1 and {MAX_QUERY_BUDGET}")
    if not 1 <= results_per_query <= MAX_RESULTS_PER_QUERY:
        raise ValueError(f"results_per_query must be between 1 and {MAX_RESULTS_PER_QUERY}")

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
        "market_role": "OFFICIAL_EXPANSION_MARKET",
        "canonical_market_coverage_unchanged": ["NO", "SE", "DE"],
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
        return {**base, "status": "BLOCKED_CONFIGURATION", "block_reason": "BRAVE_SEARCH_API_KEY_MISSING"}

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

    selected_queries = FRANCE_DISCOVERY_QUERIES[:query_budget]
    for query in selected_queries:
        query_accepted = query_rejected = query_duplicates = 0
        try:
            hits = provider.search(query.query, count=results_per_query)
            succeeded += 1
            query_status = "SUCCESS"
        except Exception as exc:
            errors.append(f"{query.query_id}: {type(exc).__name__}: {_compact(exc)[:300]}")
            query_stats.append({
                "query_id": query.query_id,
                "intent": query.intent,
                "required_domains": list(query.required_domains),
                "status": "FAILED",
                "accepted": 0,
                "rejected": 0,
                "duplicates": 0,
            })
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
            signal = france_signal_from_hit(hit, query=query, rank=rank, observed_at=now)
            if signal is None:
                rejected += 1
                query_rejected += 1
                continue
            accepted[signal.signal_id] = signal.model_dump(mode="json")
            query_accepted += 1

        query_stats.append({
            "query_id": query.query_id,
            "intent": query.intent,
            "required_domains": list(query.required_domains),
            "status": query_status,
            "accepted": query_accepted,
            "rejected": query_rejected,
            "duplicates": query_duplicates,
        })

    signals = [accepted[key] for key in sorted(accepted)]
    domains = sorted({_host(str(row.get("source_url") or "")) for row in signals if row.get("source_url")})
    status = "SUCCESS" if signals else ("VALID_ZERO" if succeeded == len(selected_queries) else "PARTIAL")
    return {
        **base,
        "status": status,
        "queries_attempted": len(selected_queries),
        "queries_succeeded": succeeded,
        "accepted_signal_count": len(signals),
        "rejected_result_count": rejected,
        "duplicate_result_count": duplicates,
        "independent_domain_count": len(domains),
        "independent_domains": domains,
        "query_stats": query_stats,
        "signals": signals,
        "errors": errors,
    }
