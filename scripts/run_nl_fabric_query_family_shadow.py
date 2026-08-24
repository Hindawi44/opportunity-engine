#!/usr/bin/env python3
"""NL FABRIC_PROCUREMENT proof wrapper over the generic query-family shadow core.

This file keeps the Dutch proof query family as test data only. Ranking,
validation, safety, and scoring live in opportunity_engine.query_family_shadow,
so NL does not own a separate discovery path.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable, Sequence

from opportunity_engine.discovery.exa_search import ExaSearchProvider
from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult, fetch_public_page
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.project_domain_boundary import FABRIC_PROCUREMENT
from opportunity_engine.query_family_shadow import run_query_family_shadow as run_generic_query_family_shadow
from opportunity_engine.search_experiment_execution_bridge_v1 import _fabric_page_candidate

MARKET_CODE = "NL"
RESULTS_PER_QUERY = 5
QUERY_FAMILY: tuple[tuple[str, str], ...] = (
    ("baseline-current-shape", "fabric textile Nederland stoffen groothandel leveranciers catalogus"),
    ("restpartijen-wholesale", "Nederland restpartijen stoffen groothandel"),
    ("stock-wholesale", "Nederland textielgroothandel voorraad stoffen"),
    ("deadstock-b2b", "Nederland deadstock stoffen B2B groothandel"),
)

ProviderFactory = Callable[[str], Any]
PageFetcher = Callable[[str], PageFetchResult]


def _default_provider_factory(api_key: str) -> ExaSearchProvider:
    return ExaSearchProvider(api_key)


def _text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


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
    provider = provider_factory(key)
    return run_generic_query_family_shadow(
        market_code=MARKET_CODE,
        project_domain=FABRIC_PROCUREMENT,
        provider_name="exa",
        search=lambda query, count: provider.search(query, count=count),
        verify_hit=lambda hit: _fabric_page_candidate(hit, page_fetcher=page_fetcher),
        query_family=query_family,
        results_per_query=results_per_query,
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
