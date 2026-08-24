#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from opportunity_engine.discovery.exa_search import ExaSearchProvider
from opportunity_engine.discovery.exa_shadow_page_verification import EXACT_LOT_CANDIDATE
from opportunity_engine.discovery.exact_lot_multihop_resolution import resolve_exact_lot_multihop
from opportunity_engine.discovery.provider_unique_page_verification import verify_provider_unique_pages
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY, classify_project_domain
from opportunity_engine.search_experiment_execution_bridge_v1 import _custom_benchmark, _market_anchored

RESULTS_PER_QUERY = 5
QUERY_FAMILIES = {
    "NO": (
        ("restlager-wholesale", "Norge kleslager restlager grossist klær"),
        ("liquidation-lot", "Norge konkurslager klær parti engros"),
        ("stocklot-wholesale", "Norge klær stocklot grossist bekledning"),
    ),
    "SE": (
        ("restlager-wholesale", "Sverige klädlager restlager grossist kläder"),
        ("liquidation-lot", "Sverige konkurslager kläder parti grossist"),
        ("stocklot-wholesale", "Sverige kläder stocklot grossist"),
    ),
    "DE": (
        ("restposten-wholesale", "Deutschland Bekleidung Restposten Großhandel Lager"),
        ("liquidation-lot", "Deutschland Insolvenzware Kleidung Restposten Großhandel"),
        ("stocklot-wholesale", "Deutschland Modeware Stocklot Großhandel"),
    ),
    "FR": (
        ("destockage-wholesale", "France déstockage vêtements grossiste stock lot"),
        ("liquidation-lot", "France liquidation stock vêtements grossiste lot"),
        ("end-series-wholesale", "France lot vêtements fin de série grossiste"),
    ),
    "NL": (
        ("restpartij-wholesale", "Nederland kledingvoorraad restpartij groothandel"),
        ("liquidation-lot", "Nederland faillissementsvoorraad kleding partij groothandel"),
        ("stocklot-wholesale", "Nederland kleding stocklot groothandel"),
    ),
    "IT": (
        ("stock-wholesale", "Italia abbigliamento stock ingrosso lotto"),
        ("liquidation-lot", "Italia liquidazione stock abbigliamento ingrosso"),
        ("end-series-wholesale", "Italia fine serie abbigliamento stock ingrosso"),
    ),
}


def _domain(url: str) -> str:
    try:
        return (urlsplit(str(url or "")).hostname or "").casefold().removeprefix("www.")
    except ValueError:
        return ""


def _exact_urls(verification: dict, multihop: dict) -> tuple[list[str], list[str]]:
    direct: set[str] = set()
    child: set[str] = set()
    for row in verification.get("verified_pages") or []:
        if not isinstance(row, dict):
            continue
        if row.get("classification") == EXACT_LOT_CANDIDATE and row.get("tool_learning_useful") is True:
            url = str(row.get("final_url") or row.get("url") or "").strip()
            if url:
                direct.add(url)
    for row in multihop.get("exact_lots") or []:
        if not isinstance(row, dict):
            continue
        url = str(row.get("final_url") or row.get("url") or "").strip()
        if url:
            child.add(url)
    return sorted(direct), sorted(child)


def _noise_count(verification: dict) -> int:
    return sum(
        int(verification.get(key) or 0)
        for key in (
            "out_of_domain_count",
            "source_intelligence_only_count",
            "info_or_legal_only_count",
            "unproven_page_count",
            "non_specific_active_filtered_count",
        )
    )


def _score(row: dict) -> int:
    return (
        int(row["exact_lot_domain_count"]) * 20
        + int(row["exact_lot_url_count"]) * 4
        + int(row["useful_clothing_signal_count"]) * 2
        - int(row["noise_count"]) * 3
        - int(row["fetch_failed_count"]) * 2
    )


def main() -> int:
    key = os.environ.get("EXA_API_KEY", "").strip()
    if not key:
        raise SystemExit("EXA_API_KEY is required")
    provider = ExaSearchProvider(key)
    market_reports: dict[str, dict] = {}

    for market, family in QUERY_FAMILIES.items():
        rows: list[dict] = []
        market_domains: set[str] = set()
        market_urls: set[str] = set()
        for query_id, query in family:
            if not _market_anchored(query, market):
                raise RuntimeError(f"query not market anchored: {market}/{query_id}")
            query_domain = classify_project_domain(text=query)
            if query_domain != CLOTHING_INVENTORY:
                raise RuntimeError(f"query escaped clothing domain: {market}/{query_id} => {query_domain}")

            hits = list(provider.search(query, count=RESULTS_PER_QUERY))[:RESULTS_PER_QUERY]
            benchmark = _custom_benchmark(
                market=market,
                query=query,
                hits=hits,
                project_domain=CLOTHING_INVENTORY,
            )
            verification = verify_provider_unique_pages(
                benchmark,
                provider="exa",
                max_page_fetches=RESULTS_PER_QUERY,
            )
            multihop = resolve_exact_lot_multihop(
                verification,
                max_root_parents=2,
                max_navigation_depth=2,
                max_links_per_page=6,
                max_navigation_page_fetches=5,
            )
            direct_urls, child_urls = _exact_urls(verification, multihop)
            exact_urls = sorted(set(direct_urls) | set(child_urls))
            exact_domains = sorted({_domain(url) for url in exact_urls if _domain(url)})
            market_urls.update(exact_urls)
            market_domains.update(exact_domains)
            row = {
                "query_id": query_id,
                "query": query,
                "search_hit_count": len(hits),
                "unique_search_domain_count": len({_domain(hit.url) for hit in hits if _domain(hit.url)}),
                "page_fetches_succeeded": int(verification.get("page_fetches_succeeded") or 0),
                "fetch_failed_count": int(verification.get("fetch_failed_count") or 0),
                "noise_count": _noise_count(verification),
                "out_of_domain_count": int(verification.get("out_of_domain_count") or 0),
                "useful_clothing_signal_count": int(verification.get("useful_clothing_signal_count") or 0),
                "direct_exact_lot_count": len(direct_urls),
                "multihop_exact_lot_count": len(child_urls),
                "exact_lot_url_count": len(exact_urls),
                "exact_lot_domain_count": len(exact_domains),
                "exact_lot_domains": exact_domains,
                "exact_lot_urls": exact_urls,
                "navigation_fetches_succeeded": int(multihop.get("navigation_page_fetches_succeeded") or 0),
            }
            row["shadow_quality_score"] = _score(row)
            rows.append(row)

        ranked = sorted(
            rows,
            key=lambda row: (
                int(row["exact_lot_domain_count"]),
                int(row["exact_lot_url_count"]),
                int(row["useful_clothing_signal_count"]),
                int(row["shadow_quality_score"]),
                -int(row["noise_count"]),
                -int(row["fetch_failed_count"]),
            ),
            reverse=True,
        )
        winner = ranked[0]
        market_reports[market] = {
            "market_code": market,
            "query_count": len(family),
            "results_per_query": RESULTS_PER_QUERY,
            "nominal_hit_budget": len(family) * RESULTS_PER_QUERY,
            "union_exact_lot_domain_count": len(market_domains),
            "union_exact_lot_domains": sorted(market_domains),
            "union_exact_lot_url_count": len(market_urls),
            "winner": winner,
            "ranking": ranked,
        }
        print(
            f"market={market} exact_union_domains={len(market_domains)} exact_union_urls={len(market_urls)} "
            f"winner={winner['query_id']} winner_exact_domains={winner['exact_lot_domain_count']} "
            f"winner_exact_urls={winner['exact_lot_url_count']} score={winner['shadow_quality_score']}"
        )
        for idx, row in enumerate(ranked, start=1):
            print(
                f"  rank={idx} query_id={row['query_id']} hits={row['search_hit_count']} "
                f"fetched={row['page_fetches_succeeded']} exact_domains={row['exact_lot_domain_count']} "
                f"exact_urls={row['exact_lot_url_count']} direct={row['direct_exact_lot_count']} "
                f"multihop={row['multihop_exact_lot_count']} useful={row['useful_clothing_signal_count']} "
                f"noise={row['noise_count']} fetch_failed={row['fetch_failed_count']} score={row['shadow_quality_score']}"
            )

    payload = {
        "schema_version": "clothing-all-markets-shadow-proof-1.0",
        "status": "SUCCESS",
        "project_domain": CLOTHING_INVENTORY,
        "provider": "exa",
        "markets": sorted(market_reports),
        "market_count": len(market_reports),
        "query_count": sum(row["query_count"] for row in market_reports.values()),
        "nominal_hit_budget": sum(row["nominal_hit_budget"] for row in market_reports.values()),
        "markets_with_exact_lot": sum(row["union_exact_lot_domain_count"] > 0 for row in market_reports.values()),
        "reports": market_reports,
        "shadow_only": True,
        "strict_exact_lot_only": True,
        "production_mutation": False,
        "automatic_query_promotion": False,
        "automatic_source_promotion": False,
        "automatic_provider_activation": False,
    }
    out = Path("artifacts/clothing-all-markets-shadow-proof-v1/report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"markets={payload['market_count']} markets_with_exact_lot={payload['markets_with_exact_lot']} "
        f"queries={payload['query_count']} nominal_hit_budget={payload['nominal_hit_budget']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
