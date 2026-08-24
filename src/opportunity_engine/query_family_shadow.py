"""Generic shadow-only query-family ranking for bounded opportunity discovery.

This module contains no market-specific query text and no provider/source
promotion.  It scores a family of search formulations for one market/domain
using a caller-supplied verifier, so the same mechanism can be reused across
markets and both project domains without creating country-specific routes.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit

from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    FABRIC_PROCUREMENT,
    classify_project_domain,
)

SCHEMA_VERSION = "query-family-shadow-1.0"
SUPPORTED_DOMAINS = frozenset({CLOTHING_INVENTORY, FABRIC_PROCUREMENT})
MARKET_ANCHORS: dict[str, tuple[str, ...]] = {
    "NO": ("norge", "norway", "norsk"),
    "SE": ("sverige", "sweden", "svensk"),
    "DE": ("deutschland", "germany", "deutsch"),
    "FR": ("france", "français", "francais"),
    "NL": ("nederland", "netherlands", "dutch"),
    "IT": ("italia", "italy", "italiano", "italiana"),
}

QueryFamily = Sequence[tuple[str, str]]
HitVerifier = Callable[[SearchHit], Mapping[str, Any]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _domain(url: object) -> str:
    try:
        host = (urlsplit(_text(url)).hostname or "").casefold()
    except ValueError:
        return ""
    return host.removeprefix("www.")


def _market_anchored(query: str, market_code: str) -> bool:
    folded = query.casefold()
    return any(anchor in folded for anchor in MARKET_ANCHORS.get(market_code, ()))


def _safety() -> dict[str, bool]:
    return {
        "shadow_only": True,
        "automatic_query_activation": False,
        "automatic_query_promotion": False,
        "production_query_mutation": False,
        "automatic_provider_activation": False,
        "automatic_source_promotion": False,
        "production_mutation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def validate_query_family(*, market_code: str, project_domain: str, query_family: QueryFamily) -> tuple[tuple[str, str], ...]:
    market = _text(market_code).upper()
    domain = _text(project_domain).upper()
    if market not in MARKET_ANCHORS:
        raise ValueError(f"unsupported market: {market}")
    if domain not in SUPPORTED_DOMAINS:
        raise ValueError(f"unsupported project domain: {domain}")

    normalized: list[tuple[str, str]] = []
    seen_ids: set[str] = set()
    seen_queries: set[str] = set()
    for query_id, query in query_family:
        qid = _text(query_id)
        q = _text(query)
        if not qid or not q:
            raise ValueError("query family entries require non-empty id and query")
        if qid in seen_ids:
            raise ValueError(f"duplicate query id: {qid}")
        folded = q.casefold()
        if folded in seen_queries:
            raise ValueError(f"duplicate query text: {q}")
        if not _market_anchored(q, market):
            raise ValueError(f"query is not {market}-anchored: {qid}")
        classified = classify_project_domain(text=q)
        if classified != domain:
            raise ValueError(f"query escaped {domain}: {qid} classified={classified}")
        seen_ids.add(qid)
        seen_queries.add(folded)
        normalized.append((qid, q))
    if not normalized:
        raise ValueError("query family must contain at least one query")
    return tuple(normalized)


def quality_score(*, accepted_domains: int, fetch_failed: int, semantic_noise: int, duplicate_domains: int) -> int:
    """Transparent shadow score; ranking evidence only, never promotion."""
    return accepted_domains * 10 - fetch_failed * 2 - semantic_noise * 4 - duplicate_domains


def evaluate_query_hits(*, query_id: str, query: str, hits: Sequence[SearchHit], verify_hit: HitVerifier) -> dict[str, Any]:
    audits = [dict(verify_hit(hit)) for hit in hits]
    raw_domains = [_domain(hit.url) for hit in hits if _domain(hit.url)]
    accepted = [row for row in audits if _text(row.get("verification_decision")).upper() == "ACCEPT"]
    rejected = [row for row in audits if _text(row.get("verification_decision")).upper() != "ACCEPT"]

    accepted_domains = sorted({
        _domain(row.get("final_url") or row.get("url"))
        for row in accepted
        if _domain(row.get("final_url") or row.get("url"))
    })
    duplicate_domains = max(0, len(raw_domains) - len(set(raw_domains)))
    fetch_failed = sum(_text(row.get("rejection_reason")) == "FETCH_FAILED" for row in rejected)
    semantic_noise = sum(
        _text(row.get("rejection_reason")) not in {"", "FETCH_FAILED"}
        for row in rejected
    )
    reasons = Counter(_text(row.get("rejection_reason")) or "UNDIAGNOSED" for row in rejected)
    fetched_count = sum(row.get("fetch_ok") is True for row in audits)
    acceptance_rate = round(len(accepted) / fetched_count, 4) if fetched_count else 0.0
    supplier_yield = round(len(accepted_domains) / len(hits), 4) if hits else 0.0

    return {
        "query_id": query_id,
        "query": query,
        "hit_count": len(hits),
        "unique_result_domain_count": len(set(raw_domains)),
        "duplicate_domain_count": duplicate_domains,
        "fetch_success_count": fetched_count,
        "fetch_failed_count": fetch_failed,
        "semantic_noise_count": semantic_noise,
        "accepted_url_count": len(accepted),
        "accepted_domain_count": len(accepted_domains),
        "accepted_domains": accepted_domains,
        "supplier_yield": supplier_yield,
        "acceptance_rate_on_fetched": acceptance_rate,
        "rejection_reason_counts": dict(sorted(reasons.items())),
        "shadow_quality_score": quality_score(
            accepted_domains=len(accepted_domains),
            fetch_failed=fetch_failed,
            semantic_noise=semantic_noise,
            duplicate_domains=duplicate_domains,
        ),
        "search_hit_audit": audits,
    }


def run_query_family_shadow(
    *,
    market_code: str,
    project_domain: str,
    provider_name: str,
    search: Callable[[str, int], Sequence[SearchHit]],
    verify_hit: HitVerifier,
    query_family: QueryFamily,
    results_per_query: int = 5,
) -> dict[str, Any]:
    if not 1 <= results_per_query <= 5:
        raise ValueError("results_per_query must be between 1 and 5")
    family = validate_query_family(
        market_code=market_code,
        project_domain=project_domain,
        query_family=query_family,
    )
    market = _text(market_code).upper()
    domain = _text(project_domain).upper()
    provider = _text(provider_name).casefold()
    if not provider:
        raise ValueError("provider_name is required")

    rows: list[dict[str, Any]] = []
    all_result_domains: set[str] = set()
    all_accepted_domains: set[str] = set()
    for query_id, query in family:
        hits = list(search(query, results_per_query))[:results_per_query]
        row = evaluate_query_hits(
            query_id=query_id,
            query=query,
            hits=hits,
            verify_hit=verify_hit,
        )
        rows.append(row)
        all_accepted_domains.update(row["accepted_domains"])
        all_result_domains.update(_domain(hit.url) for hit in hits if _domain(hit.url))

    ranked = sorted(
        rows,
        key=lambda row: (
            int(row["accepted_domain_count"]),
            int(row["shadow_quality_score"]),
            float(row["supplier_yield"]),
            -int(row["semantic_noise_count"]),
            -int(row["fetch_failed_count"]),
            row["query_id"],
        ),
        reverse=True,
    )
    ranking = [
        {
            "rank": index,
            "query_id": row["query_id"],
            "query": row["query"],
            "accepted_domain_count": row["accepted_domain_count"],
            "supplier_yield": row["supplier_yield"],
            "semantic_noise_count": row["semantic_noise_count"],
            "fetch_failed_count": row["fetch_failed_count"],
            "duplicate_domain_count": row["duplicate_domain_count"],
            "shadow_quality_score": row["shadow_quality_score"],
        }
        for index, row in enumerate(ranked, start=1)
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "status": "SUCCESS",
        "market_code": market,
        "project_domain": domain,
        "provider": provider,
        "query_count": len(family),
        "results_per_query": results_per_query,
        "nominal_hit_budget": len(family) * results_per_query,
        "query_family": [{"query_id": qid, "query": query} for qid, query in family],
        "query_results": rows,
        "ranking": ranking,
        "shadow_winner_candidate": ranking[0] if ranking else None,
        "union_unique_result_domain_count": len(all_result_domains),
        "union_accepted_domain_count": len(all_accepted_domains),
        "union_accepted_domains": sorted(all_accepted_domains),
        "interpretation_guard": (
            "Query-family ranking is shadow evidence only and cannot authorize production mutation or promotion."
        ),
        **_safety(),
    }
