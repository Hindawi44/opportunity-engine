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
QUERIES = {
    "NO": (
        "Norge restlager klær grossist parti",
        "Norge overskuddslager klær til salgs vareparti",
        "Norge kleslager restparti engros mote",
    ),
    "SE": (
        "Sverige restparti kläder grossist lager",
        "Sverige överskottslager kläder till salu parti",
        "Sverige klädlager restposten grossist mode",
    ),
    "DE": (
        "Deutschland Restposten Bekleidung Großhandel Lager",
        "Deutschland Sonderposten Kleidung zu verkaufen Großhandel",
        "Deutschland Warenlager Mode Restposten Bekleidung",
    ),
}


def _commercial_evidence(ev: dict) -> dict:
    return {
        "project_domain": ev.get("project_domain"),
        "subject_domain": ev.get("page_subject_domain"),
        "inventory": ev.get("inventory_evidence"),
        "sale": ev.get("direct_sale_evidence"),
        "price": ev.get("price_evidence"),
        "quantity": ev.get("quantity_evidence"),
        "item_specific": ev.get("item_specific_url_evidence"),
        "canonical_product": ev.get("canonical_product_detail_url_evidence"),
        "explicit_purchase": ev.get("explicit_purchase_evidence"),
        "mixed_subject": ev.get("mixed_general_merchandise_subject_evidence"),
        "info_or_legal": ev.get("info_or_legal_evidence"),
    }


def main() -> int:
    key = os.environ.get("EXA_API_KEY", "").strip()
    if not key:
        raise SystemExit("EXA_API_KEY is required")
    provider = ExaSearchProvider(key)
    reports: dict[str, dict] = {}

    for market, queries in QUERIES.items():
        all_hits = []
        seen_urls: set[str] = set()
        query_rows = []
        for query in queries:
            if not _market_anchored(query, market):
                raise RuntimeError(f"query not market anchored: {market}: {query}")
            if classify_project_domain(text=query) != CLOTHING_INVENTORY:
                raise RuntimeError(f"query escaped clothing domain: {market}: {query}")
            hits = list(provider.search(query, count=RESULTS_PER_QUERY))[:RESULTS_PER_QUERY]
            query_rows.append({
                "query": query,
                "hits": [{"title": h.title, "url": h.url, "description": h.description} for h in hits],
            })
            for hit in hits:
                if hit.url in seen_urls:
                    continue
                seen_urls.add(hit.url)
                all_hits.append(hit)

        benchmark = _custom_benchmark(
            market=market,
            query=" | ".join(queries),
            hits=all_hits,
            project_domain=CLOTHING_INVENTORY,
        )
        verification = verify_provider_unique_pages(
            benchmark,
            provider="exa",
            max_page_fetches=min(30, len(all_hits) or 1),
        )
        multihop = resolve_exact_lot_multihop(
            verification,
            max_root_parents=6,
            max_navigation_depth=3,
            max_links_per_page=12,
            max_navigation_page_fetches=30,
        )

        pages = []
        for row in verification.get("verified_pages") or []:
            if not isinstance(row, dict):
                continue
            ev = row.get("evidence") or {}
            pages.append({
                "title": row.get("title"),
                "url": row.get("url"),
                "final_url": row.get("final_url"),
                "classification": row.get("classification"),
                "fetch_ok": row.get("fetch_ok"),
                "status_code": row.get("status_code"),
                "tool_learning_useful": row.get("tool_learning_useful"),
                "evidence": {
                    "project_domain": ev.get("project_domain"),
                    "inventory": ev.get("inventory_evidence"),
                    "sale": ev.get("direct_sale_evidence"),
                    "buyer_source": ev.get("buyer_or_source_evidence"),
                    "price": ev.get("price_evidence"),
                    "quantity": ev.get("quantity_evidence"),
                    "item_specific": ev.get("item_specific_url_evidence"),
                    "b2b": ev.get("b2b_wholesale_evidence"),
                    "qualified_b2b": ev.get("qualified_b2b_sale_evidence"),
                },
            })

        root_results = []
        for row in multihop.get("root_results") or []:
            if not isinstance(row, dict):
                continue
            root_results.append({
                "root_url": row.get("root_url"),
                "final_url": row.get("final_url"),
                "classification": row.get("root_classification"),
                "navigation_role": row.get("root_navigation_role"),
                "fetch_ok": row.get("fetch_ok"),
                "navigation_link_count": row.get("navigation_link_count"),
                "navigation_links": row.get("navigation_links") or [],
                "fetch_error": row.get("fetch_error"),
            })

        navigation_results = []
        for row in multihop.get("navigation_results") or []:
            if not isinstance(row, dict):
                continue
            ev = row.get("evidence") or {}
            navigation_results.append({
                "title": row.get("title"),
                "url": row.get("url"),
                "final_url": row.get("final_url"),
                "classification": row.get("classification"),
                "fetch_ok": row.get("fetch_ok"),
                "status_code": row.get("status_code"),
                "navigation_role": row.get("navigation_role"),
                "navigation_depth": row.get("navigation_depth") or row.get("depth"),
                "navigation_chain": row.get("navigation_chain") or row.get("chain"),
                "fetch_error": row.get("fetch_error"),
                "evidence": _commercial_evidence(ev),
            })

        exact_lots = []
        for row in multihop.get("exact_lots") or []:
            if not isinstance(row, dict):
                continue
            ev = row.get("evidence") or {}
            exact_lots.append({
                "title": row.get("title"),
                "url": row.get("url"),
                "parent_url": row.get("parent_url"),
                "project_domain": ev.get("project_domain"),
                "subject_domain": ev.get("page_subject_domain"),
                "inventory": ev.get("inventory_evidence"),
                "sale": ev.get("direct_sale_evidence"),
                "price": ev.get("price_evidence"),
                "quantity": ev.get("quantity_evidence"),
                "item_specific": ev.get("item_specific_url_evidence"),
            })

        reports[market] = {
            "market": market,
            "queries": query_rows,
            "raw_hit_count": sum(len(r["hits"]) for r in query_rows),
            "unique_hit_count": len(all_hits),
            "verification_summary": {
                "fetch_succeeded": verification.get("page_fetches_succeeded"),
                "active_stock": verification.get("active_stock_signal_count"),
                "direct_exact": verification.get("exact_lot_candidate_count"),
                "out_of_domain": verification.get("out_of_domain_count"),
                "source_intelligence": verification.get("source_intelligence_only_count"),
                "unproven": verification.get("unproven_page_count"),
                "fetch_failed": verification.get("fetch_failed_count"),
            },
            "verified_pages": pages,
            "multihop_summary": {
                "eligible_roots": multihop.get("eligible_root_parent_count"),
                "navigation_attempted": multihop.get("navigation_page_fetches_attempted"),
                "navigation_succeeded": multihop.get("navigation_page_fetches_succeeded"),
                "gateways": multihop.get("gateway_page_count"),
                "exact_lots": multihop.get("exact_lot_candidate_count"),
            },
            "root_results": root_results,
            "navigation_results": navigation_results,
            "exact_lots": exact_lots,
        }

        vs = reports[market]["verification_summary"]
        ms = reports[market]["multihop_summary"]
        print(
            f"market={market} raw_hits={reports[market]['raw_hit_count']} unique_hits={len(all_hits)} "
            f"fetched={vs['fetch_succeeded']} active={vs['active_stock']} direct_exact={vs['direct_exact']} "
            f"roots={ms['eligible_roots']} nav={ms['navigation_succeeded']} multihop_exact={ms['exact_lots']} "
            f"out_of_domain={vs['out_of_domain']} unproven={vs['unproven']} fetch_failed={vs['fetch_failed']}"
        )
        for page in pages:
            ev = page["evidence"]
            print(
                f"  PAGE {page['classification']} | {page['title']} | {page['final_url'] or page['url']} | "
                f"domain={ev['project_domain']} inv={ev['inventory']} sale={ev['sale']} price={ev['price']} "
                f"qty={ev['quantity']} item={ev['item_specific']} b2b={ev['b2b']} q_b2b={ev['qualified_b2b']}"
            )
        for nav in navigation_results:
            ev = nav["evidence"]
            print(
                f"  NAV {nav['classification']} | {nav['title']} | {nav['final_url'] or nav['url']} | "
                f"role={nav['navigation_role']} depth={nav['navigation_depth']} domain={ev['project_domain']} "
                f"subject={ev['subject_domain']} inv={ev['inventory']} sale={ev['sale']} price={ev['price']} "
                f"qty={ev['quantity']} item={ev['item_specific']} canonical={ev['canonical_product']} "
                f"purchase={ev['explicit_purchase']}"
            )
        for lot in exact_lots:
            print(f"  EXACT | {lot['title']} | {lot['url']}")

    payload = {
        "schema_version": "clothing-no-se-de-search-truth-1.1",
        "status": "SUCCESS",
        "project_domain": CLOTHING_INVENTORY,
        "provider": "exa",
        "markets": list(QUERIES),
        "query_count": sum(len(v) for v in QUERIES.values()),
        "nominal_hit_budget": sum(len(v) for v in QUERIES.values()) * RESULTS_PER_QUERY,
        "reports": reports,
        "shadow_only": True,
        "production_mutation": False,
        "automatic_query_promotion": False,
        "automatic_source_promotion": False,
        "automatic_provider_activation": False,
    }
    out = Path("artifacts/clothing-no-se-de-search-truth-v1/report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
