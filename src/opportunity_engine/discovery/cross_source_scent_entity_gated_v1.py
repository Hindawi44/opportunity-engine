"""Entity-gated execution layer for Cross-Source Scent Expansion V2.

V2 remains the broad public-web discovery engine. This layer deliberately runs its
six broad discovery requests first, applies ENTITY_SCENT_QUALITY_GATE_V1 to the
resulting signals, then spends the remaining request budget only on concrete,
clustered company identities.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any, Mapping

from opportunity_engine.discovery.brave_market_signal_radar import (
    MarketRadarQuery,
    _compact,
    _default_provider_factory,
    _iso_utc,
    market_signal_from_brave_hit,
)
from opportunity_engine.discovery.cross_source_scent_expansion_v2 import (
    DEFAULT_FRESHNESS,
    DEFAULT_MAX_REQUESTS,
    DEFAULT_RESULTS_PER_QUERY,
    MAX_REQUESTS,
    MAX_RESULTS_PER_QUERY,
    SUPPORTED_MARKETS,
    ProviderFactory,
    _eligible_hit,
    _follow_up_query,
    _hit_matches_label,
    _safety_payload,
    collect_cross_source_scent_expansion_v2,
)
from opportunity_engine.discovery.entity_scent_quality_gate_v1 import (
    ENGINE_VERSION as ENTITY_GATE_VERSION,
    build_entity_scent_quality_gate,
)
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider

SCHEMA_VERSION = "cross-source-scent-entity-gated-v1-1.0"
ENGINE_VERSION = "CROSS_SOURCE_SCENT_EXPANSION_V2_ENTITY_GATED"
BASE_DISCOVERY_REQUESTS = 6


def _raw_candidates_from_discovery(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for signal in report.get("signals") or []:
        metadata = dict(signal.get("metadata") or {})
        if metadata.get("cross_source_stage") != "DISCOVERY":
            continue
        label = _compact(metadata.get("scent_label"))
        if not label:
            continue
        candidates.append(
            {
                "market_code": _compact(signal.get("source_country")).upper(),
                "label": label,
                "score": int(metadata.get("scent_score") or 0),
                "source_url": _compact(signal.get("source_url")),
                "source_title": _compact(signal.get("title")),
                "parent_query_id": _compact(metadata.get("query_id")),
            }
        )
    return candidates


def _classification_by_url(gate: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    classified: dict[str, dict[str, Any]] = {}
    for item in gate.get("source_intelligence") or []:
        url = _compact(item.get("source_url"))
        if url:
            classified[url] = {
                "classification": "SOURCE_INTELLIGENCE",
                "entity_label": None,
                "entity_key": None,
                "entity_cluster_score": None,
            }
    for scent in gate.get("entity_scents") or []:
        for evidence in scent.get("evidence") or []:
            url = _compact(evidence.get("source_url"))
            if not url:
                continue
            classified[url] = {
                "classification": "ENTITY_SCENT",
                "entity_label": scent.get("label"),
                "entity_key": scent.get("entity_key"),
                "entity_cluster_score": scent.get("score"),
                "entity_evidence_count": scent.get("evidence_count"),
                "entity_independent_source_count": scent.get("independent_source_count"),
            }
    return classified


def collect_entity_gated_cross_source_scent_expansion_v2(
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
    if not BASE_DISCOVERY_REQUESTS <= max_requests <= MAX_REQUESTS:
        raise ValueError(f"max_requests must be between {BASE_DISCOVERY_REQUESTS} and {MAX_REQUESTS}")

    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    env = environment if environment is not None else os.environ
    api_key = _compact(env.get("BRAVE_SEARCH_API_KEY")) or _compact(env.get("BRAVE_API_KEY"))

    # Force V2 to perform discovery only. Its minimum budget is exactly the six
    # broad discovery queries, so no generic V2 scent can consume follow-up budget.
    discovery = collect_cross_source_scent_expansion_v2(
        observed_at=now,
        environment=env,
        provider_factory=provider_factory,
        results_per_query=results_per_query,
        max_requests=BASE_DISCOVERY_REQUESTS,
        freshness=freshness,
    )
    if discovery.get("status") == "BLOCKED_CONFIGURATION":
        return {
            **discovery,
            "schema_version": SCHEMA_VERSION,
            "engine_version": ENGINE_VERSION,
            "entity_scent_quality_gate_version": ENTITY_GATE_VERSION,
        }

    raw_candidates = _raw_candidates_from_discovery(discovery)
    gate = build_entity_scent_quality_gate(raw_candidates)
    ranked_scents = list(gate.get("qualified_entity_scents") or [])
    classification = _classification_by_url(gate)

    accepted: dict[str, dict[str, Any]] = {}
    seen_urls: set[str] = set()
    for original in discovery.get("signals") or []:
        payload = dict(original)
        url = _compact(payload.get("source_url"))
        metadata = dict(payload.get("metadata") or {})
        gate_info = classification.get(url)
        if gate_info:
            metadata.update(
                {
                    "entity_scent_quality_gate": ENTITY_GATE_VERSION,
                    "entity_scent_classification": gate_info.get("classification"),
                    "entity_label": gate_info.get("entity_label"),
                    "entity_key": gate_info.get("entity_key"),
                    "entity_cluster_score": gate_info.get("entity_cluster_score"),
                    "entity_evidence_count": gate_info.get("entity_evidence_count"),
                    "entity_independent_source_count": gate_info.get("entity_independent_source_count"),
                }
            )
        payload["metadata"] = metadata
        signal_id = _compact(payload.get("signal_id"))
        if signal_id:
            accepted[signal_id] = payload
        if url:
            seen_urls.add(url)

    providers: dict[str, SearchProvider] = {
        market: provider_factory(market, api_key, freshness)
        for market in SUPPORTED_MARKETS
    }
    requests_made = int(discovery.get("requests_made") or 0)
    errors = list(discovery.get("errors") or [])
    follow_up_diagnostics: list[dict[str, Any]] = []
    followed_scents: list[dict[str, Any]] = []

    for scent in ranked_scents:
        if requests_made >= max_requests:
            break
        market = _compact(scent.get("market_code")).upper()
        label = _compact(scent.get("label"))
        if not market or not label:
            continue
        query_text = _follow_up_query(label, market)
        query_id = f"{market.casefold()}-entity-scent-follow-{len(followed_scents) + 1}"
        requests_made += 1
        diag: dict[str, Any] = {
            "query_id": query_id,
            "market_code": market,
            "stage": "ENTITY_FOLLOW_UP",
            "scent_label": label,
            "entity_key": scent.get("entity_key"),
            "entity_cluster_score": scent.get("score"),
            "entity_evidence_count": scent.get("evidence_count"),
            "result_count": 0,
            "accepted_count": 0,
        }
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
            signal = market_signal_from_brave_hit(
                hit,
                market_code=market,
                query=radar_query,
                rank=rank,
                observed_at=now,
            )
            if signal is None:
                continue
            payload = signal.model_dump(mode="json")
            url = _compact(payload.get("source_url"))
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            metadata = dict(payload.get("metadata") or {})
            metadata.update(
                {
                    "cross_source_engine": ENGINE_VERSION,
                    "cross_source_stage": "ENTITY_FOLLOW_UP",
                    "entity_scent_quality_gate": ENTITY_GATE_VERSION,
                    "entity_scent_classification": "ENTITY_SCENT",
                    "entity_label": label,
                    "entity_key": scent.get("entity_key"),
                    "entity_cluster_score": scent.get("score"),
                    "entity_base_score": scent.get("base_score"),
                    "entity_evidence_count": scent.get("evidence_count"),
                    "entity_independent_source_count": scent.get("independent_source_count"),
                    "parent_scent_url": scent.get("source_url"),
                    "parent_query_id": scent.get("parent_query_id"),
                    "source_page_verification_required": True,
                    "promotion_to_opportunity_allowed": False,
                }
            )
            payload["metadata"] = metadata
            payload["source"] = "Cross-source scent expansion V2 + entity quality gate V1"
            accepted[str(payload["signal_id"])] = payload
            diag["accepted_count"] = int(diag["accepted_count"]) + 1
            follow_hits += 1

        followed_scents.append(
            {
                **scent,
                "follow_up_query": query_text,
                "new_follow_up_signal_count": follow_hits,
            }
        )
        follow_up_diagnostics.append(diag)

    status = "SUCCESS" if accepted else ("PARTIAL_RETRIEVAL" if errors else "VALID_ZERO")
    return {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "base_engine_version": discovery.get("engine_version"),
        "entity_scent_quality_gate_version": ENTITY_GATE_VERSION,
        "generated_at": _iso_utc(now),
        "status": status,
        "market_coverage": list(SUPPORTED_MARKETS),
        "request_budget": max_requests,
        "requests_made": requests_made,
        "results_per_query": results_per_query,
        "freshness": freshness,
        "discovery_request_count": int(discovery.get("discovery_request_count") or 0),
        "follow_up_request_count": len(follow_up_diagnostics),
        "accepted_signal_count": len(accepted),
        "strong_scent_count": len(ranked_scents),
        "followed_scent_count": len(followed_scents),
        "entity_cluster_count": int(gate.get("entity_cluster_count") or 0),
        "source_intelligence_count": int(gate.get("source_intelligence_count") or 0),
        "top_scents": ranked_scents[:8],
        "followed_scents": followed_scents,
        "entity_scent_quality_gate": gate,
        "discovery_diagnostics": list(discovery.get("discovery_diagnostics") or []),
        "follow_up_diagnostics": follow_up_diagnostics,
        "signals": [accepted[key] for key in sorted(accepted)],
        "errors": errors,
        "source_page_verification_required": True,
        **_safety_payload(),
    }
