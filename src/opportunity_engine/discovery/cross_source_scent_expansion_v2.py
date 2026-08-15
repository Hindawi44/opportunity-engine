"""Cross-source scent expansion trial for Sweden and Germany.

This module deliberately runs outside the production daily decision path at first.
It searches the wider public web for clothing insolvency/liquidation scents, ranks
those scents, then follows the strongest names across sources. Every result is an
unverified EARLY_SIGNAL only; nothing here can promote directly to an opportunity.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
import re
from typing import Any, Callable, Mapping, Sequence

from opportunity_engine.discovery.brave_market_signal_radar import (
    MarketRadarQuery,
    _compact,
    _default_provider_factory,
    _iso_utc,
    market_signal_from_brave_hit,
)
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider

SCHEMA_VERSION = "cross-source-scent-expansion-v2-1.0"
ENGINE_VERSION = "CROSS_SOURCE_SCENT_EXPANSION_V2"
SUPPORTED_MARKETS = ("DE", "SE")
DEFAULT_RESULTS_PER_QUERY = 8
MAX_RESULTS_PER_QUERY = 10
DEFAULT_MAX_REQUESTS = 12
MAX_REQUESTS = 24
DEFAULT_FRESHNESS = "pm"
MIN_SCENT_SCORE = 55

ProviderFactory = Callable[[str, str, str | None], SearchProvider]


@dataclass(frozen=True, slots=True)
class ScentQuery:
    query_id: str
    market_code: str
    query: str


DISCOVERY_QUERIES: dict[str, tuple[ScentQuery, ...]] = {
    "DE": (
        ScentQuery(
            "de-cross-insolvency-stock",
            "DE",
            '(Insolvenz OR Insolvenzverfahren OR Geschäftsaufgabe) '
            '(Modehaus OR Bekleidungsgeschäft OR Textilhandel OR Schuhgeschäft) '
            '(Warenbestand OR Lager OR Verwertung OR Auktion)',
        ),
        ScentQuery(
            "de-cross-liquidation-stock",
            "DE",
            '(Lagerauflösung OR Räumungsverkauf OR Restposten OR Warenbestand) '
            '(Mode OR Bekleidung OR Textil OR Schuhe) (Firma OR GmbH OR Geschäft)',
        ),
        ScentQuery(
            "de-cross-administrator-fashion",
            "DE",
            '(Insolvenzverwalter OR Insolvenzbekanntmachung) '
            '(Bekleidung OR Mode OR Textil OR Schuhe) '
            '(Verkauf OR Warenbestand OR Verwertung)',
        ),
    ),
    "SE": (
        ScentQuery(
            "se-cross-bankruptcy-stock",
            "SE",
            '(konkurs OR konkursbo OR avveckling) '
            '(klädbutik OR modebutik OR textilhandel OR skoaffär) '
            '(varulager OR lager OR auktion OR försäljning)',
        ),
        ScentQuery(
            "se-cross-trustee-fashion",
            "SE",
            '(konkursförvaltare OR "konkurs inledd") '
            '(kläder OR konfektion OR textil OR skor) '
            '(varulager OR försäljning OR auktion)',
        ),
        ScentQuery(
            "se-cross-clearance-stock",
            "SE",
            '(utförsäljning OR lagerrensning OR butikstömning OR restlager) '
            '(kläder OR mode OR textil OR skor) (företag OR butik OR AB)',
        ),
    ),
}

_CLOTHING_TERMS = {
    "DE": ("bekleidung", "mode", "modehaus", "textil", "schuhe", "schuhgeschäft", "kleidung"),
    "SE": ("kläder", "klader", "mode", "klädbutik", "kladbutik", "textil", "skor", "konfektion"),
}
_EVENT_TERMS = {
    "DE": ("insolvenz", "geschäftsaufgabe", "lagerauflösung", "räumungsverkauf", "restposten", "auktion", "versteigerung", "liquidation"),
    "SE": ("konkurs", "avveckling", "utförsäljning", "lagerrensning", "auktion", "försäljning", "likvidation"),
}
_INVENTORY_TERMS = {
    "DE": ("warenbestand", "warenlager", "lagerbestand", "verwertung", "restposten", "lagerauflösung"),
    "SE": ("varulager", "lagerparti", "butikslager", "restlager", "lager", "utförsäljning"),
}
_OFF_TOPIC_TERMS = {
    "DE": ("restaurant", "gastronomie", "küche", "maschinen", "fahrzeuge", "werkzeuge"),
    "SE": ("restaurang", "storkök", "kök", "maskiner", "fordon", "verktyg"),
}
_COMPANY_MARKERS = {
    "DE": ("gmbh", " ag", " kg", " ug"),
    "SE": (" ab",),
}
_STOP_WORDS = {
    "de": {"der", "die", "das", "und", "von", "zur", "zum", "in", "im", "insolvenz", "insolvenzverfahren", "auktion", "versteigerung"},
    "se": {"och", "i", "på", "pa", "konkurs", "auktion", "utförsäljning", "utforsaljning"},
}


def _safety_payload() -> dict[str, bool]:
    return {
        "signal_only": True,
        "promotion_to_opportunity_allowed": False,
        "analysis_eligible": False,
        "top5_eligible": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _contains(text: str, terms: Sequence[str]) -> bool:
    folded = text.casefold()
    return any(term.casefold() in folded for term in terms)


def _eligible_hit(hit: SearchHit, market_code: str) -> bool:
    market = market_code.upper()
    title = _compact(hit.title).casefold()
    description = _compact(hit.description).casefold()
    combined = f"{title} {description}"
    title_clothing = _contains(title, _CLOTHING_TERMS[market])
    body_clothing = _contains(description, _CLOTHING_TERMS[market])
    has_event = _contains(combined, _EVENT_TERMS[market])
    if _contains(title, _OFF_TOPIC_TERMS[market]) and not title_clothing:
        return False
    return has_event and (title_clothing or body_clothing)


def _scent_score(hit: SearchHit, market_code: str) -> int:
    market = market_code.upper()
    title = _compact(hit.title).casefold()
    description = _compact(hit.description).casefold()
    combined = f"{title} {description}"
    score = 0
    if _contains(title, _CLOTHING_TERMS[market]):
        score += 25
    elif _contains(description, _CLOTHING_TERMS[market]):
        score += 10
    if _contains(title, _EVENT_TERMS[market]):
        score += 20
    elif _contains(description, _EVENT_TERMS[market]):
        score += 10
    if _contains(combined, _INVENTORY_TERMS[market]):
        score += 25
    if _contains(title, _COMPANY_MARKERS[market]):
        score += 15
    if len(_compact(hit.title)) >= 12:
        score += 5
    return min(100, score)


def _normalize_label(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" -–—|:,.;")


def _extract_scent_label(title: str, market_code: str) -> str | None:
    text = _normalize_label(_compact(title))
    if not text:
        return None
    market = market_code.upper()
    marker_pattern = r"\b(?:GmbH|AG|KG|UG|AB)\b"
    match = re.search(rf"(.{{3,90}}?{marker_pattern})", text, flags=re.IGNORECASE)
    if match:
        candidate = match.group(1)
    else:
        candidate = re.split(r"\s+[|–—-]\s+|:\s+", text, maxsplit=1)[0]
    candidate = re.sub(
        r"^(?:Insolvenz(?:verfahren)?(?:\s+der|\s+von)?|Konkurs(?:bo)?(?:\s+för)?|Auktion(?:\s+av)?|Versteigerung(?:\s+von)?)\s+",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    candidate = _normalize_label(candidate)
    if len(candidate) < 4 or len(candidate) > 100:
        return None
    lowered = candidate.casefold()
    if lowered in _STOP_WORDS[market.casefold()]:
        return None
    return candidate


def _label_tokens(label: str, market_code: str) -> set[str]:
    stop = _STOP_WORDS[market_code.casefold()]
    return {
        token
        for token in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+", label.casefold())
        if len(token) >= 3 and token not in stop
    }


def _hit_matches_label(hit: SearchHit, label: str, market_code: str) -> bool:
    tokens = _label_tokens(label, market_code)
    if not tokens:
        return False
    haystack = f"{_compact(hit.title)} {_compact(hit.description)}".casefold()
    overlap = sum(1 for token in tokens if token in haystack)
    needed = 1 if len(tokens) == 1 else 2
    return overlap >= needed


def _follow_up_query(label: str, market_code: str) -> str:
    if market_code.upper() == "DE":
        return f'"{label}" (Warenbestand OR Lagerauflösung OR Insolvenzauktion OR Versteigerung OR Verkauf)'
    return f'"{label}" (varulager OR konkursauktion OR utförsäljning OR auktion OR försäljning)'


def collect_cross_source_scent_expansion_v2(
    *,
    observed_at: datetime | None = None,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory = _default_provider_factory,
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
    max_requests: int = DEFAULT_MAX_REQUESTS,
    freshness: str | None = DEFAULT_FRESHNESS,
) -> dict[str, Any]:
    if not 1 <= results_per_query <= MAX_RESULTS_PER_QUERY:
        raise ValueError(f"results_per_query must be between 1 and {MAX_RESULTS_PER_QUERY}")
    if not 6 <= max_requests <= MAX_REQUESTS:
        raise ValueError(f"max_requests must be between 6 and {MAX_REQUESTS}")

    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    env = environment if environment is not None else os.environ
    api_key = _compact(env.get("BRAVE_SEARCH_API_KEY")) or _compact(env.get("BRAVE_API_KEY"))
    if not api_key:
        return {
            "schema_version": SCHEMA_VERSION,
            "engine_version": ENGINE_VERSION,
            "generated_at": _iso_utc(now),
            "status": "BLOCKED_CONFIGURATION",
            "block_reason": "BRAVE_SEARCH_API_KEY_MISSING",
            "requests_made": 0,
            "signals": [],
            "top_scents": [],
            **_safety_payload(),
        }

    providers: dict[str, SearchProvider] = {}
    for market in SUPPORTED_MARKETS:
        providers[market] = provider_factory(market, api_key, freshness)

    requests_made = 0
    errors: list[str] = []
    raw_scent_candidates: list[dict[str, Any]] = []
    accepted: dict[str, dict[str, Any]] = {}
    seen_urls: set[str] = set()
    discovery_diagnostics: list[dict[str, Any]] = []

    # Phase 1: six broad, market-wide discovery queries. Germany intentionally runs first.
    for market in SUPPORTED_MARKETS:
        for query in DISCOVERY_QUERIES[market]:
            if requests_made >= max_requests:
                break
            requests_made += 1
            diag = {"query_id": query.query_id, "market_code": market, "stage": "DISCOVERY", "result_count": 0, "accepted_count": 0}
            try:
                hits = providers[market].search(query.query, count=results_per_query)
                diag["result_count"] = len(hits)
            except Exception as exc:
                message = f"{query.query_id}: {type(exc).__name__}: {_compact(exc)[:300]}"
                errors.append(message)
                diag["error"] = message
                discovery_diagnostics.append(diag)
                continue
            for rank, hit in enumerate(hits, start=1):
                if not isinstance(hit, SearchHit) or not _eligible_hit(hit, market):
                    continue
                radar_query = MarketRadarQuery(query_id=query.query_id, query=query.query)
                signal = market_signal_from_brave_hit(hit, market_code=market, query=radar_query, rank=rank, observed_at=now)
                if signal is None:
                    continue
                payload = signal.model_dump(mode="json")
                url = _compact(payload.get("source_url"))
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                score = _scent_score(hit, market)
                label = _extract_scent_label(hit.title, market)
                metadata = dict(payload.get("metadata") or {})
                metadata.update({
                    "cross_source_engine": ENGINE_VERSION,
                    "cross_source_stage": "DISCOVERY",
                    "scent_score": score,
                    "scent_label": label,
                    "source_page_verification_required": True,
                    "promotion_to_opportunity_allowed": False,
                })
                payload["metadata"] = metadata
                payload["source"] = "Cross-source scent expansion V2"
                accepted[str(payload["signal_id"])] = payload
                diag["accepted_count"] = int(diag["accepted_count"]) + 1
                if label and score >= MIN_SCENT_SCORE:
                    raw_scent_candidates.append({
                        "market_code": market,
                        "label": label,
                        "score": score,
                        "source_url": url,
                        "source_title": _compact(hit.title),
                        "parent_query_id": query.query_id,
                    })
            discovery_diagnostics.append(diag)

    # Unique scents, strongest first; Germany wins ties because it is the larger weak market.
    unique_scents: dict[tuple[str, str], dict[str, Any]] = {}
    for scent in raw_scent_candidates:
        key = (scent["market_code"], scent["label"].casefold())
        current = unique_scents.get(key)
        if current is None or int(scent["score"]) > int(current["score"]):
            unique_scents[key] = scent
    ranked_scents = sorted(
        unique_scents.values(),
        key=lambda item: (-int(item["score"]), 0 if item["market_code"] == "DE" else 1, item["label"].casefold()),
    )

    follow_up_diagnostics: list[dict[str, Any]] = []
    followed_scents: list[dict[str, Any]] = []
    for scent in ranked_scents:
        if requests_made >= max_requests:
            break
        market = str(scent["market_code"])
        label = str(scent["label"])
        query_text = _follow_up_query(label, market)
        query_id = f"{market.casefold()}-scent-follow-{len(followed_scents) + 1}"
        requests_made += 1
        diag = {"query_id": query_id, "market_code": market, "stage": "FOLLOW_UP", "scent_label": label, "result_count": 0, "accepted_count": 0}
        try:
            hits = providers[market].search(query_text, count=results_per_query)
            diag["result_count"] = len(hits)
        except Exception as exc:
            message = f"{query_id}: {type(exc).__name__}: {_compact(exc)[:300]}"
            errors.append(message)
            diag["error"] = message
            follow_up_diagnostics.append(diag)
            continue
        follow_hits = 0
        for rank, hit in enumerate(hits, start=1):
            if not isinstance(hit, SearchHit):
                continue
            if not _hit_matches_label(hit, label, market) or not _eligible_hit(hit, market):
                continue
            radar_query = MarketRadarQuery(query_id=query_id, query=query_text)
            signal = market_signal_from_brave_hit(hit, market_code=market, query=radar_query, rank=rank, observed_at=now)
            if signal is None:
                continue
            payload = signal.model_dump(mode="json")
            url = _compact(payload.get("source_url"))
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            metadata = dict(payload.get("metadata") or {})
            metadata.update({
                "cross_source_engine": ENGINE_VERSION,
                "cross_source_stage": "FOLLOW_UP",
                "scent_score": scent["score"],
                "scent_label": label,
                "parent_scent_url": scent["source_url"],
                "parent_query_id": scent["parent_query_id"],
                "source_page_verification_required": True,
                "promotion_to_opportunity_allowed": False,
            })
            payload["metadata"] = metadata
            payload["source"] = "Cross-source scent expansion V2"
            accepted[str(payload["signal_id"])] = payload
            diag["accepted_count"] = int(diag["accepted_count"]) + 1
            follow_hits += 1
        followed_scents.append({**scent, "follow_up_query": query_text, "new_follow_up_signal_count": follow_hits})
        follow_up_diagnostics.append(diag)

    status = "SUCCESS" if accepted else ("PARTIAL_RETRIEVAL" if errors else "VALID_ZERO")
    return {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "generated_at": _iso_utc(now),
        "status": status,
        "market_coverage": list(SUPPORTED_MARKETS),
        "request_budget": max_requests,
        "requests_made": requests_made,
        "results_per_query": results_per_query,
        "freshness": freshness,
        "discovery_request_count": len(discovery_diagnostics),
        "follow_up_request_count": len(follow_up_diagnostics),
        "accepted_signal_count": len(accepted),
        "strong_scent_count": len(ranked_scents),
        "followed_scent_count": len(followed_scents),
        "top_scents": ranked_scents[:8],
        "followed_scents": followed_scents,
        "discovery_diagnostics": discovery_diagnostics,
        "follow_up_diagnostics": follow_up_diagnostics,
        "signals": [accepted[key] for key in sorted(accepted)],
        "errors": errors,
        "source_page_verification_required": True,
        **_safety_payload(),
    }
