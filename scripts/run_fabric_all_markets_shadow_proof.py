#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

from opportunity_engine.discovery.exa_search import ExaSearchProvider
from opportunity_engine.discovery.keyword_shadow_verification import fetch_public_page
from opportunity_engine.project_domain_boundary import FABRIC_PROCUREMENT
from opportunity_engine.query_family_shadow import run_query_family_shadow
from opportunity_engine.search_experiment_execution_bridge_v1 import _fabric_page_candidate

QUERY_FAMILIES = {
    "NO": (
        ("stock-wholesale", "Norge metervare lager grossist tekstil"),
        ("roll-wholesale", "Norge stoffruller lager grossist tekstil"),
        ("surplus-wholesale", "Norge fabric surplus wholesale metervare"),
        ("deadstock-b2b", "Norge fabric deadstock B2B metervare"),
    ),
    "SE": (
        ("stock-wholesale", "Sverige tyg lager grossist textil"),
        ("roll-wholesale", "Sverige tygrullar lager grossist textil"),
        ("surplus-wholesale", "Sverige fabric surplus wholesale tyg"),
        ("deadstock-b2b", "Sverige fabric deadstock B2B tyg"),
    ),
    "DE": (
        ("stock-wholesale", "Deutschland Meterware Lager Großhandel Gewebe"),
        ("restposten-wholesale", "Deutschland Restposten Meterware Großhandel Gewebe"),
        ("surplus-wholesale", "Deutschland fabric surplus wholesale Meterware"),
        ("deadstock-b2b", "Deutschland fabric deadstock B2B Meterware"),
    ),
    "FR": (
        ("stock-wholesale", "France tissu stock grossiste textile"),
        ("destockage-wholesale", "France déstockage tissus grossiste textile"),
        ("roll-wholesale", "France rouleaux de tissu stock grossiste"),
        ("deadstock-b2b", "France fabric deadstock B2B tissus"),
    ),
    "IT": (
        ("stock-wholesale", "Italia tessuti magazzino ingrosso textile"),
        ("roll-wholesale", "Italia rotoli di tessuto magazzino ingrosso"),
        ("surplus-wholesale", "Italia tessuti scorte ingrosso textile"),
        ("deadstock-b2b", "Italia fabric deadstock B2B tessuti ingrosso"),
    ),
}


def main() -> int:
    key = os.environ.get("EXA_API_KEY", "").strip()
    if not key:
        raise SystemExit("EXA_API_KEY is required")
    provider = ExaSearchProvider(key)
    reports = {}
    total_accepted = 0
    for market, family in QUERY_FAMILIES.items():
        report = run_query_family_shadow(
            market_code=market,
            project_domain=FABRIC_PROCUREMENT,
            provider_name="exa",
            search=lambda query, count: provider.search(query, count=count),
            verify_hit=lambda hit: _fabric_page_candidate(hit, page_fetcher=fetch_public_page),
            query_family=family,
            results_per_query=5,
        )
        reports[market] = report
        total_accepted += int(report["union_accepted_domain_count"])
        winner = report.get("shadow_winner_candidate") or {}
        print(
            f"market={market} accepted_union={report['union_accepted_domain_count']} "
            f"unique_union={report['union_unique_result_domain_count']} "
            f"winner={winner.get('query_id')} winner_accepted={winner.get('accepted_domain_count')} "
            f"winner_score={winner.get('shadow_quality_score')}"
        )
        for row in report["ranking"]:
            print(
                f"  rank={row['rank']} query_id={row['query_id']} accepted={row['accepted_domain_count']} "
                f"yield={row['supplier_yield']:.4f} noise={row['semantic_noise_count']} "
                f"fetch_failed={row['fetch_failed_count']} duplicates={row['duplicate_domain_count']} "
                f"score={row['shadow_quality_score']}"
            )
    payload = {
        "schema_version": "fabric-all-markets-shadow-proof-1.0",
        "status": "SUCCESS",
        "project_domain": FABRIC_PROCUREMENT,
        "provider": "exa",
        "markets": sorted(reports),
        "market_count": len(reports),
        "query_count": sum(int(r["query_count"]) for r in reports.values()),
        "nominal_hit_budget": sum(int(r["nominal_hit_budget"]) for r in reports.values()),
        "sum_market_union_accepted_domain_count": total_accepted,
        "reports": reports,
        "shadow_only": True,
        "production_mutation": False,
        "automatic_query_promotion": False,
        "automatic_source_promotion": False,
        "automatic_provider_activation": False,
    }
    out = Path("artifacts/fabric-all-markets-shadow-proof-v1/report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"markets={payload['market_count']} queries={payload['query_count']} nominal_hit_budget={payload['nominal_hit_budget']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
