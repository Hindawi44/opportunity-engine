"""Bounded keyword discovery lab for fashion liquidation search terms.

The lab evaluates search-query quality before any query is allowed into a live
market-discovery feed. It is deliberately read-only: it searches public web
results, scores keyword precision/yield, and emits evidence. It never promotes
an opportunity, contacts a seller, bids, reserves, buys, or persists into the
production opportunity pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import html
import re
import unicodedata
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider


SCHEMA_VERSION = "keyword-discovery-lab-1.0"
LAB_FAMILY = "KEYWORD_DISCOVERY_LAB_V1"
DEFAULT_MARKET = "IT"
DEFAULT_KEYWORD_LIMIT = 10
MAX_KEYWORD_LIMIT = 50
DEFAULT_RESULTS_PER_KEYWORD = 5
MAX_RESULTS_PER_KEYWORD = 10


@dataclass(frozen=True, slots=True)
class KeywordCandidate:
    keyword_id: str
    family: str
    query: str


ITALY_KEYWORD_CANDIDATES: tuple[KeywordCandidate, ...] = (
    KeywordCandidate("it-stock-ingrosso", "STOCK_WHOLESALE", "stock abbigliamento ingrosso"),
    KeywordCandidate("it-lotti-stock", "STOCKLOTS", "lotti abbigliamento stock"),
    KeywordCandidate(
        "it-rimanenze-magazzino",
        "WAREHOUSE_REMAINDERS",
        "rimanenze di magazzino abbigliamento",
    ),
    KeywordCandidate(
        "it-liquidazione-magazzino",
        "WAREHOUSE_LIQUIDATION",
        "liquidazione magazzino abbigliamento",
    ),
    KeywordCandidate(
        "it-stock-firmato-ingrosso",
        "BRANDED_WHOLESALE",
        "stock abbigliamento firmato ingrosso",
    ),
    KeywordCandidate(
        "it-invenduto-stock",
        "UNSOLD_INVENTORY",
        "abbigliamento invenduto stock",
    ),
    KeywordCandidate("it-stockista", "STOCKIST", "stockista abbigliamento"),
    KeywordCandidate(
        "it-lotti-fallimentari",
        "BANKRUPTCY_LOTS",
        "lotti fallimentari abbigliamento",
    ),
    KeywordCandidate(
        "it-cessazione-stock",
        "BUSINESS_CLOSURE",
        "cessazione attività abbigliamento stock",
    ),
    KeywordCandidate(
        "it-vendita-stock-magazzino",
        "WAREHOUSE_STOCK_SALE",
        "vendita stock abbigliamento magazzino",
    ),
)

_B2B_TERMS = (
    "b2b",
    "ingrosso",
    "all'ingrosso",
    "grossista",
    "grossisti",
    "stockista",
    "stockisti",
    "fornitore",
    "fornitori",
    "rivenditore",
    "rivenditori",
    "wholesale",
    "distributore",
    "distributori",
)
_STOCK_TERMS = (
    "stock abbigliamento",
    "stock moda",
    "stock firmato",
    "lotto",
    "lotti",
    "rimanenze",
    "rimanenze di magazzino",
    "invenduto",
    "invenduti",
    "magazzino abbigliamento",
    "fine serie",
    "deadstock",
    "stocklot",
    "stocklots",
)
_LIQUIDATION_TERMS = (
    "liquidazione",
    "liquidazione giudiziale",
    "fallimento",
    "fallimentare",
    "fallimentari",
    "insolvenza",
    "cessazione attività",
    "cessazione attivita",
    "chiusura attività",
    "chiusura attivita",
    "chiusura negozio",
    "procedura concorsuale",
    "vendita giudiziaria",
    "vendita fallimentare",
    "asta giudiziaria",
    "svendita totale",
)
_COMMERCIAL_EVIDENCE_TERMS = (
    "prezzo",
    "prezzi",
    "eur",
    "euro",
    "pezzo",
    "pezzi",
    "quantità",
    "quantita",
    "minimo ordine",
    "ordine minimo",
    "moq",
    "pronta consegna",
    "disponibile",
    "disponibili",
)
_SELLER_EVIDENCE_TERMS = (
    "s.r.l",
    "srl",
    "s.p.a",
    "spa",
    "s.n.c",
    "snc",
    "s.a.s",
    "sas",
    "partita iva",
    "p.iva",
    "azienda",
    "società",
    "societa",
    "contatti",
)
_ITALY_GEO_TERMS = (
    "italia",
    "italy",
    "milano",
    "prato",
    "brescia",
    "bologna",
    "roma",
    "napoli",
    "como",
    "biella",
    "firenze",
    "toscana",
    "lombardia",
    "veneto",
    "emilia-romagna",
)
_RETAIL_TERMS = (
    "acquista online",
    "shop online",
    "carrello",
    "spedizione gratuita",
    "nuova collezione",
    "taglie disponibili",
    "taglia",
    "saldi online",
)
_NEWS_TERMS = (
    "notizia",
    "notizie",
    "cronaca",
    "articolo",
    "giornale",
    "quotidiano",
    "news",
)
_BLOCKED_RETAIL_HOSTS = (
    "amazon.",
    "ebay.",
    "zalando.",
    "temu.",
    "aliexpress.",
)

ProviderFactory = Callable[[str, str, str | None], SearchProvider]


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalise(value: object) -> str:
    return unicodedata.normalize("NFKC", html.unescape(_compact(value))).casefold()


def _term_present(text: str, term: str) -> bool:
    """Match complete terms, preventing substring leaks such as asta in vasta."""
    normalized_text = _normalise(text)
    normalized_term = _normalise(term)
    if not normalized_term:
        return False
    return re.search(
        rf"(?<!\w){re.escape(normalized_term)}(?!\w)",
        normalized_text,
        flags=re.UNICODE,
    ) is not None


def _matched(text: str, terms: Sequence[str]) -> list[str]:
    return sorted({term for term in terms if _term_present(text, term)})


def _host(raw_url: object) -> str:
    try:
        return (urlsplit(_compact(raw_url)).hostname or "").casefold().rstrip(".")
    except ValueError:
        return ""


def _is_false_positive(text: str, host: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    retail = _matched(text, _RETAIL_TERMS)
    news = _matched(text, _NEWS_TERMS)
    blocked_host = next((marker for marker in _BLOCKED_RETAIL_HOSTS if marker in host), None)
    if retail:
        reasons.append("RETAIL_LANGUAGE")
    if news:
        reasons.append("NEWS_LANGUAGE")
    if blocked_host:
        reasons.append("CONSUMER_MARKETPLACE")
    return bool(reasons), reasons


def classify_hit(hit: SearchHit, *, rank: int) -> dict[str, Any]:
    title = _compact(hit.title)
    description = _compact(hit.description)
    text = f"{title} {description}".strip()
    host = _host(hit.url)
    b2b_terms = _matched(text, _B2B_TERMS)
    stock_terms = _matched(text, _STOCK_TERMS)
    liquidation_terms = _matched(text, _LIQUIDATION_TERMS)
    commercial_terms = _matched(text, _COMMERCIAL_EVIDENCE_TERMS)
    seller_terms = _matched(text, _SELLER_EVIDENCE_TERMS)
    geo_terms = _matched(text, _ITALY_GEO_TERMS)
    italy_domain = host.endswith(".it")
    false_positive, false_positive_reasons = _is_false_positive(text, host)

    # Actionable here means useful for keyword-quality measurement only. It does
    # not mean the result is a verified opportunity.
    actionable = bool(stock_terms) and bool(b2b_terms or liquidation_terms) and not false_positive
    return {
        "rank": rank,
        "title": title,
        "url": _compact(hit.url),
        "host": host,
        "provider": _compact(hit.provider),
        "b2b": bool(b2b_terms),
        "stock_or_lot": bool(stock_terms),
        "liquidation_or_closure": bool(liquidation_terms),
        "quantity_or_price": bool(commercial_terms),
        "seller_identity": bool(seller_terms),
        "italy_relevance": bool(geo_terms) or italy_domain,
        "false_positive": false_positive,
        "actionable_for_keyword_lab": actionable,
        "matched_terms": {
            "b2b": b2b_terms,
            "stock_or_lot": stock_terms,
            "liquidation_or_closure": liquidation_terms,
            "quantity_or_price": commercial_terms,
            "seller_identity": seller_terms,
            "geography": geo_terms,
        },
        "false_positive_reasons": false_positive_reasons,
    }


def _ratio(records: Sequence[Mapping[str, Any]], field: str) -> float:
    if not records:
        return 0.0
    return sum(1 for record in records if bool(record.get(field))) / len(records)


def score_keyword(
    candidate: KeywordCandidate,
    hits: Sequence[SearchHit],
) -> dict[str, Any]:
    records = [
        classify_hit(hit, rank=rank)
        for rank, hit in enumerate(hits, start=1)
        if isinstance(hit, SearchHit)
    ]
    b2b_ratio = _ratio(records, "b2b")
    stock_ratio = _ratio(records, "stock_or_lot")
    liquidation_ratio = _ratio(records, "liquidation_or_closure")
    commercial_ratio = _ratio(records, "quantity_or_price")
    seller_ratio = _ratio(records, "seller_identity")
    geo_ratio = _ratio(records, "italy_relevance")
    false_positive_ratio = _ratio(records, "false_positive")
    clean_ratio = max(0.0, 1.0 - false_positive_ratio) if records else 0.0
    actionable_yield = _ratio(records, "actionable_for_keyword_lab")

    weighted = (
        b2b_ratio * 25
        + stock_ratio * 25
        + liquidation_ratio * 20
        + commercial_ratio * 10
        + seller_ratio * 10
        + geo_ratio * 5
        + clean_ratio * 5
    )
    score = round(weighted, 2)
    decision = "PROMOTE" if score >= 80 else ("SHADOW" if score >= 60 else "REJECT")
    unique_domains = sorted({record["host"] for record in records if record.get("host")})

    return {
        "keyword_id": candidate.keyword_id,
        "family": candidate.family,
        "query": candidate.query,
        "result_count": len(records),
        "unique_domain_count": len(unique_domains),
        "score": score,
        "decision": decision,
        "metrics": {
            "b2b_ratio": round(b2b_ratio, 4),
            "stock_or_lot_ratio": round(stock_ratio, 4),
            "liquidation_or_closure_ratio": round(liquidation_ratio, 4),
            "quantity_or_price_ratio": round(commercial_ratio, 4),
            "seller_identity_ratio": round(seller_ratio, 4),
            "italy_relevance_ratio": round(geo_ratio, 4),
            "false_positive_ratio": round(false_positive_ratio, 4),
            "actionable_yield": round(actionable_yield, 4),
        },
        "results": records,
    }


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


def run_keyword_discovery_lab(
    *,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory = _default_provider_factory,
    candidates: Sequence[KeywordCandidate] = ITALY_KEYWORD_CANDIDATES,
    keyword_limit: int = DEFAULT_KEYWORD_LIMIT,
    results_per_keyword: int = DEFAULT_RESULTS_PER_KEYWORD,
    freshness: str | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate a bounded keyword pack without altering production discovery."""
    if not 1 <= keyword_limit <= min(MAX_KEYWORD_LIMIT, len(candidates)):
        raise ValueError(f"keyword_limit must be between 1 and {min(MAX_KEYWORD_LIMIT, len(candidates))}")
    if not 1 <= results_per_keyword <= MAX_RESULTS_PER_KEYWORD:
        raise ValueError(
            f"results_per_keyword must be between 1 and {MAX_RESULTS_PER_KEYWORD}"
        )

    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    env = environment or {}
    api_key = _compact(env.get("BRAVE_SEARCH_API_KEY")) or _compact(env.get("BRAVE_API_KEY"))

    base: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "lab_family": LAB_FAMILY,
        "generated_at": now.isoformat(),
        "market": DEFAULT_MARKET,
        "keyword_limit": keyword_limit,
        "results_per_keyword": results_per_keyword,
        "freshness": freshness,
        "production_write_enabled": False,
        "promotion_to_live_engine_enabled": False,
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
            "evaluations": [],
            "ranking": [],
            "errors": [],
        }

    try:
        provider = provider_factory(DEFAULT_MARKET, api_key, freshness)
    except Exception as exc:
        return {
            **base,
            "status": "BLOCKED_RETRIEVAL",
            "block_reason": "PROVIDER_INITIALIZATION_FAILED",
            "evaluations": [],
            "ranking": [],
            "errors": [f"{type(exc).__name__}: {_compact(exc)[:300]}"],
        }

    evaluations: list[dict[str, Any]] = []
    errors: list[str] = []
    succeeded = 0
    for candidate in candidates[:keyword_limit]:
        try:
            hits = provider.search(candidate.query, count=results_per_keyword)
            evaluations.append(score_keyword(candidate, hits))
            succeeded += 1
        except Exception as exc:
            errors.append(
                f"{candidate.keyword_id}: {type(exc).__name__}: {_compact(exc)[:300]}"
            )
            evaluations.append(
                {
                    "keyword_id": candidate.keyword_id,
                    "family": candidate.family,
                    "query": candidate.query,
                    "result_count": 0,
                    "unique_domain_count": 0,
                    "score": 0.0,
                    "decision": "ERROR",
                    "metrics": {},
                    "results": [],
                }
            )

    ranking = [
        {
            "rank": rank,
            "keyword_id": item["keyword_id"],
            "family": item["family"],
            "query": item["query"],
            "score": item["score"],
            "decision": item["decision"],
            "actionable_yield": item.get("metrics", {}).get("actionable_yield", 0.0),
            "false_positive_ratio": item.get("metrics", {}).get("false_positive_ratio", 0.0),
        }
        for rank, item in enumerate(
            sorted(
                evaluations,
                key=lambda item: (
                    -float(item.get("score", 0.0)),
                    -float(item.get("metrics", {}).get("actionable_yield", 0.0)),
                    str(item.get("keyword_id", "")),
                ),
            ),
            start=1,
        )
    ]
    promoted = sum(1 for item in evaluations if item.get("decision") == "PROMOTE")
    shadow = sum(1 for item in evaluations if item.get("decision") == "SHADOW")
    rejected = sum(1 for item in evaluations if item.get("decision") == "REJECT")
    status = "SUCCESS" if succeeded == keyword_limit else (
        "PARTIAL_RETRIEVAL" if succeeded else "BLOCKED_RETRIEVAL"
    )
    return {
        **base,
        "status": status,
        "block_reason": None if succeeded else "ALL_KEYWORD_QUERIES_FAILED",
        "queries_attempted": keyword_limit,
        "queries_succeeded": succeeded,
        "promote_count": promoted,
        "shadow_count": shadow,
        "reject_count": rejected,
        "error_count": len(errors),
        "ranking": ranking,
        "evaluations": evaluations,
        "errors": errors,
    }
