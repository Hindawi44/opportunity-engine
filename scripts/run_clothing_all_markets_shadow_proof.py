#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

from opportunity_engine.discovery.exa_search import ExaSearchProvider
from opportunity_engine.discovery.exact_lot_multihop_resolution import resolve_exact_lot_multihop
from opportunity_engine.discovery.provider_unique_page_verification import verify_provider_unique_pages
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY, classify_project_domain
from opportunity_engine.search_experiment_execution_bridge_v1 import _custom_benchmark, _market_anchored

RESULTS_PER_QUERY = 5
DIAGNOSTIC_QUERIES = {
    "NO": ("restlager-wholesale", "Norge kleslager restlager grossist klær"),
    "SE": ("restlager-wholesale", "Sverige klädlager restlager grossist kläder"),
    "DE": ("restposten-wholesale", "Deutschland Bekleidung Restposten Großhandel Lager"),
    "FR": ("destockage-wholesale", "France déstockage vêtements grossiste stock lot"),
    "NL": ("restpartij-wholesale", "Nederland kledingvoorraad restpartij groothandel"),
    "IT": ("liquidation-lot", "Italia liquidazione stock abbigliamento ingrosso"),
}


def _compact_page(row: dict) -> dict:
    evidence = row.get("evidence") or {}
    return {
        "title": row.get("title"),
        "url": row.get("url"),
        "final_url": row.get("final_url"),
        "classification": row.get("classification"),
        "fetch_ok": row.get("fetch_ok"),
        "status_code": row.get("status_code"),
        "tool_learning_useful": row.get("tool_learning_useful"),
        "evidence": {
            "project_domain": evidence.get("project_domain"),
            "inventory_evidence": evidence.get("inventory_evidence"),
            "direct_sale_evidence": evidence.get("direct_sale_evidence"),
            "buyer_or_source_evidence": evidence.get("buyer_or_source_evidence"),
            "info_or_legal_evidence": evidence.get("info_or_legal_evidence"),
            "price_evidence": evidence.get("price_evidence"),
            "quantity_evidence": evidence.get("quantity_evidence"),
            "item_specific_url_evidence": evidence.get("item_specific_url_evidence"),
        },
    }


def main() -> int:
    key = os.environ.get("EXA_API_KEY", "").strip()
    if not key:
        raise SystemExit("EXA_API_KEY is required")
    provider = ExaSearchProvider(key)
    reports = {}

    for market, (query_id, query) in DIAGNOSTIC_QUERIES.items():
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
        compact_pages = [_compact_page(dict(row)) for row in verification.get("verified_pages") or [] if isinstance(row, dict)]
        reports[market] = {
            "market_code": market,
            "query_id": query_id,
            "query": query,
            "search_hits": [
                {"title": hit.title, "url": hit.url, "description": hit.description}
                for hit in hits
            ],
            "verification_summary": {
                "provider_unique_url_count": verification.get("provider_unique_url_count"),
                "page_fetches_succeeded": verification.get("page_fetches_succeeded"),
                "useful_clothing_signal_count": verification.get("useful_clothing_signal_count"),
                "exact_lot_candidate_count": verification.get("exact_lot_candidate_count"),
                "active_stock_signal_count": verification.get("active_stock_signal_count"),
                "non_specific_active_filtered_count": verification.get("non_specific_active_filtered_count"),
                "out_of_domain_count": verification.get("out_of_domain_count"),
                "source_intelligence_only_count": verification.get("source_intelligence_only_count"),
                "info_or_legal_only_count": verification.get("info_or_legal_only_count"),
                "unproven_page_count": verification.get("unproven_page_count"),
                "fetch_failed_count": verification.get("fetch_failed_count"),
            },
            "verified_pages": compact_pages,
            "multihop_summary": {
                "eligible_root_parent_count": multihop.get("eligible_root_parent_count"),
                "gateway_page_count": multihop.get("gateway_page_count"),
                "exact_lot_candidate_count": multihop.get("exact_lot_candidate_count"),
                "navigation_page_fetches_succeeded": multihop.get("navigation_page_fetches_succeeded"),
            },
            "multihop_exact_lots": [
                {
                    "title": row.get("title"),
                    "url": row.get("url"),
                    "final_url": row.get("final_url"),
                    "parent_url": row.get("parent_url"),
                }
                for row in multihop.get("exact_lots") or []
                if isinstance(row, dict)
            ],
        }
        summary = reports[market]["verification_summary"]
        print(
            f"market={market} hits={len(hits)} fetched={summary['page_fetches_succeeded']} "
            f"useful={summary['useful_clothing_signal_count']} active={summary['active_stock_signal_count']} "
            f"direct_exact={summary['exact_lot_candidate_count']} multihop_exact={multihop.get('exact_lot_candidate_count') or 0} "
            f"out_of_domain={summary['out_of_domain_count']} unproven={summary['unproven_page_count']} "
            f"fetch_failed={summary['fetch_failed_count']}"
        )
        for page in compact_pages:
            ev = page["evidence"]
            print(
                f"  {page['classification']} | {page['title']} | {page['final_url'] or page['url']} | "
                f"domain={ev['project_domain']} inv={ev['inventory_evidence']} sale={ev['direct_sale_evidence']} "
                f"price={ev['price_evidence']} qty={ev['quantity_evidence']} item={ev['item_specific_url_evidence']}"
            )

    payload = {
        "schema_version": "clothing-search-truth-diagnostic-1.0",
        "status": "SUCCESS",
        "project_domain": CLOTHING_INVENTORY,
        "provider": "exa",
        "market_count": len(reports),
        "query_count": len(reports),
        "nominal_hit_budget": len(reports) * RESULTS_PER_QUERY,
        "reports": reports,
        "shadow_only": True,
        "production_mutation": False,
        "automatic_query_promotion": False,
        "automatic_source_promotion": False,
        "automatic_provider_activation": False,
    }
    out = Path("artifacts/clothing-all-markets-shadow-proof-v1/report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
