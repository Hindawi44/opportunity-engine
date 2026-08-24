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
# Focus this diagnostic on markets that already produced an ACTIVE_STOCK_SIGNAL.
DIAGNOSTIC_QUERIES = {
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
            "b2b_wholesale_evidence": evidence.get("b2b_wholesale_evidence"),
            "qualified_b2b_sale_evidence": evidence.get("qualified_b2b_sale_evidence"),
        },
    }


def _root_row(row: dict) -> dict:
    return {
        "root_url": row.get("root_url"),
        "root_classification": row.get("root_classification"),
        "root_navigation_role": row.get("root_navigation_role"),
        "fetch_ok": row.get("fetch_ok"),
        "final_url": row.get("final_url"),
        "navigation_link_count": row.get("navigation_link_count"),
        "navigation_links": row.get("navigation_links") or [],
        "fetch_error": row.get("fetch_error"),
    }


def _navigation_row(row: dict) -> dict:
    evidence = row.get("evidence") or {}
    return {
        "url": row.get("url"),
        "final_url": row.get("final_url"),
        "depth": row.get("depth"),
        "classification": row.get("classification"),
        "navigation_role": row.get("navigation_role"),
        "fetch_ok": row.get("fetch_ok"),
        "fetch_error": row.get("fetch_error"),
        "project_domain": evidence.get("project_domain"),
        "page_subject_domain": evidence.get("page_subject_domain"),
        "inventory": evidence.get("inventory_evidence"),
        "direct_sale": evidence.get("direct_sale_evidence"),
        "price": evidence.get("price_evidence"),
        "quantity": evidence.get("quantity_evidence"),
        "item_specific": evidence.get("item_specific_url_evidence"),
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
        if classify_project_domain(text=query) != CLOTHING_INVENTORY:
            raise RuntimeError(f"query escaped clothing domain: {market}/{query_id}")

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
            max_links_per_page=10,
            max_navigation_page_fetches=10,
        )
        compact_pages = [
            _compact_page(dict(row))
            for row in verification.get("verified_pages") or []
            if isinstance(row, dict)
        ]
        root_results = [
            _root_row(dict(row))
            for row in multihop.get("root_results") or []
            if isinstance(row, dict)
        ]
        navigation_results = [
            _navigation_row(dict(row))
            for row in multihop.get("navigation_results") or []
            if isinstance(row, dict)
        ]
        reports[market] = {
            "market_code": market,
            "query_id": query_id,
            "query": query,
            "search_hits": [
                {"title": hit.title, "url": hit.url, "description": hit.description}
                for hit in hits
            ],
            "verified_pages": compact_pages,
            "root_results": root_results,
            "navigation_results": navigation_results,
            "multihop_summary": {
                "eligible_root_parent_count": multihop.get("eligible_root_parent_count"),
                "gateway_page_count": multihop.get("gateway_page_count"),
                "exact_lot_candidate_count": multihop.get("exact_lot_candidate_count"),
                "navigation_page_fetches_attempted": multihop.get("navigation_page_fetches_attempted"),
                "navigation_page_fetches_succeeded": multihop.get("navigation_page_fetches_succeeded"),
            },
            "multihop_exact_lots": multihop.get("exact_lots") or [],
        }

        active = sum(page["classification"] == "ACTIVE_STOCK_SIGNAL" for page in compact_pages)
        print(
            f"market={market} hits={len(hits)} active={active} roots={len(root_results)} "
            f"nav_attempted={multihop.get('navigation_page_fetches_attempted') or 0} "
            f"nav_succeeded={multihop.get('navigation_page_fetches_succeeded') or 0} "
            f"gateways={multihop.get('gateway_page_count') or 0} "
            f"exact={multihop.get('exact_lot_candidate_count') or 0}"
        )
        for root in root_results:
            print(
                f"  ROOT {root['final_url'] or root['root_url']} role={root['root_navigation_role']} "
                f"links={root['navigation_link_count']} -> {root['navigation_links']}"
            )
        for nav in navigation_results:
            print(
                f"  NAV depth={nav['depth']} role={nav['navigation_role']} class={nav['classification']} "
                f"url={nav['final_url'] or nav['url']} domain={nav['project_domain']} "
                f"subject={nav['page_subject_domain']} inv={nav['inventory']} sale={nav['direct_sale']} "
                f"price={nav['price']} qty={nav['quantity']} item={nav['item_specific']}"
            )

    payload = {
        "schema_version": "clothing-multihop-navigation-truth-1.0",
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
