#!/usr/bin/env python3
"""Shadow-only NL FABRIC_PROCUREMENT query-family benchmark.

The benchmark compares a small family of Dutch fabric-procurement queries with
one fixed Exa budget per query and the existing production fabric verifier.
It produces ranking evidence only. It cannot mutate production queries, promote
sources, activate providers, or change automatic learning state.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit

from opportunity_engine.discovery.exa_search import ExaSearchProvider
from opportunity_engine.discovery.keyword_shadow_verification import (
    PageFetchResult,
    fetch_public_page,
)
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.project_domain_boundary import FABRIC_PROCUREMENT, classify_project_domain
from opportunity_engine.search_experiment_execution_bridge_v1 import _fabric_page_candidate

SCHEMA_VERSION = "nl-fabric-query-family-shadow-1.0"
MARKET_CODE = "NL"
RESULTS_PER_QUERY = 5

QUERY_FAMILY: tuple[tuple[str, str], ...] = (
    (
        "baseline-current-shape",
        "fabric textile Nederland stoffen groothandel leveranciers catalogus",
    ),
    (
        "restpartijen-wholesale",
        "Nederland restpartijen stoffen groothandel",
    ),
    (
        "stock-wholesale",
        "Nederland textielgroothandel voorraad stoffen",
    ),
    (
        "deadstock-b2b",
        "Nederland deadstock stoffen B2B groothandel",
    ),
)

ProviderFactory = Callable[[str], Any]
PageFetcher = Callable[[str], PageFetchResult]


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


def _default_provider_factory(api_key: str) -> ExaSearchProvider:
    return ExaSearchProvider(api_key)


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


def _validate_family(query_family: Sequence[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
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
        if "nederland" not in folded:
            raise ValueError(f"query is not NL-anchored: {qid}")
        if classify_project_domain(text=q) != FABRIC_PROCUREMENT:
            raise ValueError(f"query escaped FABRIC_PROCUREMENT: {qid}")
        seen_ids.add(qid)
        seen_queries.add(folded)
        normalized.append((qid, q))
    if not normalized:
        raise ValueError("query family must contain at least one query")
    return tuple(normalized)


def _quality_score(*, accepted_domains: int, fetch_failed: int, semantic_noise: int, duplicate_domains: int) -> int:
    """Transparent bounded shadow score; ranking evidence only, never promotion."""
    return (
        accepted_domains * 10
        - fetch_failed * 2
        - semantic_noise * 4
        - duplicate_domains
    )


def _query_result(
    *,
    query_id: str,
    query: str,
    hits: Sequence[SearchHit],
    page_fetcher: PageFetcher,
) -> dict[str, Any]:
    audits = [_fabric_page_candidate(hit, page_fetcher=page_fetcher) for hit in hits]
    raw_domains = [_domain(hit.url) for hit in hits if _domain(hit.url)]
    accepted = [row for row in audits if row.get("verification_decision") == "ACCEPT"]
    rejected = [row for row in audits if row.get("verification_decision") != "ACCEPT"]

    accepted_domains = sorted({
        _domain(row.get("final_url") or row.get("url"))
        for row in accepted
        if _domain(row.get("final_url") or row.get("url"))
    })
    unique_raw_domains = set(raw_domains)
    duplicate_domains = max(0, len(raw_domains) - len(unique_raw_domains))
    fetch_failed = sum(row.get("rejection_reason") == "FETCH_FAILED" for row in rejected)
    semantic_noise = sum(
        row.get("rejection_reason") not in {None, "FETCH_FAILED"}
        for row in rejected
    )
    reasons = Counter(_text(row.get("rejection_reason")) or "UNDIAGNOSED" for row in rejected)
    fetched_count = sum(row.get("fetch_ok") is True for row in audits)
    acceptance_rate = round(len(accepted) / fetched_count, 4) if fetched_count else 0.0
    supplier_yield = round(len(accepted_domains) / len(hits), 4) if hits else 0.0
    score = _quality_score(
        accepted_domains=len(accepted_domains),
        fetch_failed=fetch_failed,
        semantic_noise=semantic_noise,
        duplicate_domains=duplicate_domains,
    )

    return {
        "query_id": query_id,
        "query": query,
        "hit_count": len(hits),
        "unique_result_domain_count": len(unique_raw_domains),
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
        "shadow_quality_score": score,
        "search_hit_audit": audits,
    }


def run_query_family_shadow(
    *,
    exa_api_key: str,
    results_per_query: int = RESULTS_PER_QUERY,
    query_family: Sequence[tuple[str, str]] = QUERY_FAMILY,
    provider_factory: ProviderFactory = _default_provider_factory,
    page_fetcher: PageFetcher = fetch_public_page,
) -> dict[str, Any]:
    key = _text(exa_api_key)
    if not key:
        raise ValueError("EXA_API_KEY is required")
    if not 1 <= results_per_query <= 5:
        raise ValueError("results_per_query must be between 1 and 5")
    family = _validate_family(query_family)

    provider = provider_factory(key)
    rows: list[dict[str, Any]] = []
    all_accepted_domains: set[str] = set()
    all_result_domains: set[str] = set()

    for query_id, query in family:
        hits = list(provider.search(query, count=results_per_query))
        row = _query_result(
            query_id=query_id,
            query=query,
            hits=hits,
            page_fetcher=page_fetcher,
        )
        rows.append(row)
        all_accepted_domains.update(row["accepted_domains"])
        all_result_domains.update(
            _domain(hit.url) for hit in hits if _domain(hit.url)
        )

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
        "market_code": MARKET_CODE,
        "project_domain": FABRIC_PROCUREMENT,
        "provider": "exa",
        "query_count": len(family),
        "results_per_query": results_per_query,
        "nominal_hit_budget": len(family) * results_per_query,
        "query_family": [
            {"query_id": query_id, "query": query}
            for query_id, query in family
        ],
        "query_results": rows,
        "ranking": ranking,
        "shadow_winner_candidate": ranking[0] if ranking else None,
        "union_unique_result_domain_count": len(all_result_domains),
        "union_accepted_domain_count": len(all_accepted_domains),
        "union_accepted_domains": sorted(all_accepted_domains),
        "interpretation_guard": (
            "Ranking is single-run shadow evidence only. It does not authorize query promotion or production mutation."
        ),
        **_safety(),
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--results-per-query", type=int, default=RESULTS_PER_QUERY)
    args = parser.parse_args()

    report = run_query_family_shadow(
        exa_api_key=os.environ.get("EXA_API_KEY", ""),
        results_per_query=args.results_per_query,
    )
    _write_json(Path(args.output), report)

    print(f"status={report['status']}")
    print(f"query_count={report['query_count']}")
    print(f"nominal_hit_budget={report['nominal_hit_budget']}")
    print(f"union_accepted_domains={report['union_accepted_domain_count']}")
    winner = report.get("shadow_winner_candidate") or {}
    print(f"winner={winner.get('query_id')}")
    for row in report["ranking"]:
        print(
            f"rank={row['rank']} query_id={row['query_id']} "
            f"accepted_domains={row['accepted_domain_count']} "
            f"yield={row['supplier_yield']:.4f} "
            f"noise={row['semantic_noise_count']} fetch_failed={row['fetch_failed_count']} "
            f"duplicates={row['duplicate_domain_count']} score={row['shadow_quality_score']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
