#!/usr/bin/env python3
"""Run the unified Exa Exact-Lot + Multi-Hop route as a checkpoint source.

All six clothing markets stay on the same Search -> Verification -> Multi-Hop ->
Exact-Lot path. Generic zero-yield recall and bounded commercial-anchor expansion
remain query stages inside the same runtime. Commercial anchors are discovery
hints only; they are never qualification evidence.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import unquote, urlsplit

from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    CONFIRMED_SALE,
    ITEM_LISTING,
    apply_post_verification_top5_hard_gate,
    write_discovery_artifacts,
)
from opportunity_engine.discovery.commercial_anchor_query_expansion import (
    MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET,
    build_commercial_anchor_queries,
)
from opportunity_engine.discovery.exa_exact_lot_shadow_hunt import MARKET_EXACT_LOT_QUERIES
from opportunity_engine.discovery.exa_search import ExaSearchProvider
from opportunity_engine.discovery.exa_shadow_page_verification import (
    ACTIVE_STOCK_SIGNAL,
    EXACT_LOT_CANDIDATE,
)
from opportunity_engine.discovery.exact_lot_multihop_resolution import resolve_exact_lot_multihop
from opportunity_engine.discovery.provider_unique_page_verification import verify_provider_unique_pages
from opportunity_engine.discovery.unified_opportunity_report import write_unified_opportunity_report
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY, classify_project_domain
from opportunity_engine.search_experiment_execution_bridge_v1 import _custom_benchmark, _market_anchored


RESULTS_PER_QUERY = 5
COMMERCIAL_ANCHOR_THIN_YIELD_THRESHOLD = 3
COMMERCIAL_ANCHOR_MIN_UNIQUE_DISCOVERY_HITS = 8
COMMERCIAL_ANCHOR_MIN_UNIQUE_DISCOVERY_HITS_BY_MARKET = {"DE": 6}
DIRECT_STRICT_EVIDENCE_RESCUE = "QUALIFIED_B2B_STRICT_EVIDENCE_V1"
MARKET_CURRENCIES = {
    "NO": "NOK",
    "SE": "SEK",
    "DE": "EUR",
    "FR": "EUR",
    "IT": "EUR",
    "NL": "EUR",
}
MARKET_EXACT_LOT_QUERY_PACKS: dict[str, tuple[str, ...]] = {
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
    "FR": (MARKET_EXACT_LOT_QUERIES["FR"],),
    "IT": (MARKET_EXACT_LOT_QUERIES["IT"],),
    "NL": (MARKET_EXACT_LOT_QUERIES["NL"],),
}

# Generic, source-neutral recall. It still runs only after primary strict yield = 0.
MARKET_ZERO_YIELD_RECALL_QUERIES: dict[str, tuple[str, ...]] = {
    "SE": ("Sverige restpartier kläder grossist säljes parti",),
    "FR": ("France déstockage vêtements grossiste stock lot",),
    "IT": ("Italia liquidazione stock abbigliamento ingrosso",),
    "NL": ("Nederland kledingvoorraad restpartij groothandel",),
}


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _commercial_anchor_min_unique_discovery_hits(market: str) -> int:
    """Return the narrow per-market anchor gate without changing global defaults.

    Germany gets a lower gate only because a live, evidence-backed wholesaler
    anchor (Salzmann Restwaren) has already recovered strict Exact-Lots when the
    primary discovery route was thin. All other markets retain the global gate.
    """
    return COMMERCIAL_ANCHOR_MIN_UNIQUE_DISCOVERY_HITS_BY_MARKET.get(
        market.upper(), COMMERCIAL_ANCHOR_MIN_UNIQUE_DISCOVERY_HITS
    )


def _title_from_url(url: str) -> str:
    path = unquote(urlsplit(url).path or "").strip("/")
    token = path.rsplit("/", 1)[-1] if path else ""
    token = token.replace("_", " ").replace("-", " ")
    title = _compact(token)
    if title and not title.isdigit():
        return title[:500]
    if title:
        return f"Clothing Exact-Lot {title}"
    return "Verified clothing Exact-Lot"


def _subject_domain(title: str, url: str) -> str:
    path_words = (
        unquote(urlsplit(url).path or "")
        .replace("-", " ")
        .replace("_", " ")
        .replace("/", " ")
    )
    return classify_project_domain(text=_compact(f"{title} {path_words}"))


def _strict_exact_evidence(*, row: Mapping[str, Any], require_subject_evidence: bool) -> bool:
    evidence = row.get("evidence") or {}
    if not isinstance(evidence, Mapping):
        return False
    url = _compact(row.get("final_url") or row.get("url"))
    title = _compact(row.get("title")) or _title_from_url(url)
    subject_ok = evidence.get("page_subject_domain") == CLOTHING_INVENTORY
    if not require_subject_evidence:
        subject_ok = _subject_domain(title, url) == CLOTHING_INVENTORY
    return bool(
        url
        and evidence.get("project_domain") == CLOTHING_INVENTORY
        and subject_ok
        and evidence.get("item_specific_url_evidence") is True
        and evidence.get("inventory_evidence") is True
        and evidence.get("direct_sale_evidence") is True
        and evidence.get("price_evidence") is True
        and evidence.get("quantity_evidence") is True
    )


def _direct_row_is_rescuable_strict_exact(raw: Mapping[str, Any]) -> bool:
    """Rescue only a qualified B2B direct page whose strict Exact-Lot proof is complete.

    This does not treat ACTIVE_STOCK_SIGNAL generally as an Exact-Lot. The narrow
    rescue exists for the verifier path that proves B2B sale evidence after the
    base classifier has already assigned ACTIVE_STOCK_SIGNAL. Brand or anchor
    presence is irrelevant and never qualification evidence.
    """
    evidence = raw.get("evidence") or {}
    return bool(
        raw.get("classification") == ACTIVE_STOCK_SIGNAL
        and isinstance(evidence, Mapping)
        and evidence.get("qualified_b2b_sale_evidence") is True
        and _strict_exact_evidence(row=raw, require_subject_evidence=False)
    )


def _exact_lot_rows(
    verification: Mapping[str, Any], multihop: Mapping[str, Any]
) -> list[dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in verification.get("verified_pages") or []:
        if not isinstance(raw, Mapping):
            continue
        classification = raw.get("classification")
        rescued = _direct_row_is_rescuable_strict_exact(raw)
        if classification != EXACT_LOT_CANDIDATE and not rescued:
            continue
        if not _strict_exact_evidence(row=raw, require_subject_evidence=False):
            continue
        row = dict(raw)
        url = _compact(row.get("final_url") or row.get("url"))
        if not url or url in seen:
            continue
        seen.add(url)
        row["url"] = url
        row["final_url"] = url
        row["exact_lot_origin"] = "DIRECT_SEARCH_RESULT"
        if rescued:
            row["direct_strict_evidence_rescue"] = DIRECT_STRICT_EVIDENCE_RESCUE
        accepted.append(row)

    for raw in multihop.get("exact_lots") or []:
        if not isinstance(raw, Mapping):
            continue
        if not _strict_exact_evidence(row=raw, require_subject_evidence=True):
            continue
        row = dict(raw)
        url = _compact(row.get("final_url") or row.get("url"))
        if not url or url in seen:
            continue
        seen.add(url)
        row["url"] = url
        row["final_url"] = url
        row["exact_lot_origin"] = "MULTI_HOP"
        accepted.append(row)

    return accepted


def _candidate_from_exact_lot(row: Mapping[str, Any], *, market: str) -> dict[str, Any]:
    url = _compact(row.get("final_url") or row.get("url"))
    title = _compact(row.get("title")) or _title_from_url(url)
    origin = _compact(row.get("exact_lot_origin")) or "STRICT_EXACT_LOT"
    evidence = row.get("evidence") or {}
    price_detected = evidence.get("price_evidence") is True
    quantity_detected = evidence.get("quantity_evidence") is True
    bounded_context = (
        "Strict Exact-Lot evidence: CLOTHING_INVENTORY subject, item-specific URL, inventory, "
        "direct sale, and source-native numeric price and quantity patterns were verified on the "
        "exact public page. Source values still require normalization before financial analysis."
    )
    missing_information = [
        "normalized source-native price value for financial analysis",
        "normalized source-native quantity value for financial analysis",
        "condition",
        "seller or company identity",
        "pickup or shipping terms",
    ]
    confirmed_information = [
        "clothing domain",
        "item-specific page",
        "inventory evidence",
        "direct-sale evidence",
        "source-native numeric price evidence" if price_detected else "price evidence",
        "source-native numeric quantity evidence" if quantity_detected else "quantity evidence",
    ]
    return {
        "title": title,
        "scenario": "LARGE_LOT_SALE",
        "opportunity_state": CONFIRMED_SALE,
        "reason": f"Exa {origin} passed the strict clothing Exact-Lot gate.",
        "page_role": ITEM_LISTING,
        "source_urls": [url],
        "canonical_urls": [url],
        "found_by_queries": [_compact(row.get("query"))] if _compact(row.get("query")) else [],
        "source_providers": ["EXA"],
        "evidence_signals": [
            "CLOTHING_INVENTORY",
            "ITEM_SPECIFIC_URL",
            "INVENTORY_PRESENT",
            "DIRECT_SALE_PRESENT",
            "PRICE_PRESENT",
            "QUANTITY_PRESENT",
        ],
        "descriptions": [],
        "inventory_type": "BULK_CLOTHING_LOT",
        "listing_status": ACTIVE,
        "opportunity_identity": url,
        "identity_stable": True,
        "source_native_price_evidence_detected": price_detected,
        "source_native_quantity_evidence_detected": quantity_detected,
        "source_value_normalization_required": True,
        "verification": [
            {
                "url": url,
                "title": title,
                "listing_status": ACTIVE,
                "page_role": ITEM_LISTING,
                "opportunity_identity": url,
                "identity_stable": True,
                "clothing_inventory_evidence": evidence.get("project_domain") == CLOTHING_INVENTORY,
                "sale_evidence": evidence.get("direct_sale_evidence") is True,
                "price_evidence": price_detected,
                "quantity_evidence": quantity_detected,
                "source_value_normalization_required": True,
                "verification_content_match": True,
                "bounded_context": bounded_context,
                "verified": True,
            }
        ],
        "verification_succeeded": True,
        "false_positive_guard_triggered": False,
        "discovery_score": 80,
        "discovery_band": "HIGH",
        "score_breakdown": {"strict_exact_lot_gate": 80},
        "why_opportunity": [
            "Exact public item/lot page was fetched successfully.",
            "Clothing domain, direct sale, and source-native numeric price and quantity evidence are present.",
        ],
        "confirmed_information": confirmed_information,
        "missing_information": missing_information,
        "next_verification_step": (
            "Normalize the already verified source-native price and quantity values, then confirm "
            "condition, seller identity and pickup/shipping terms before financial analysis."
        ),
        "top5_eligible": True,
        "analysis_eligible": False,
        "textile_category": "CLOTHING_INVENTORY",
        "market_code": market,
    }


def build_checkpoint_result_from_exact_lots(
    exact_lots: list[Mapping[str, Any]],
    *,
    market: str,
    query_count: int,
    hit_count: int,
    verification: Mapping[str, Any],
    multihop: Mapping[str, Any],
) -> dict[str, Any]:
    candidates = [_candidate_from_exact_lot(row, market=market) for row in exact_lots]
    direct_rescue_count = sum(
        1 for row in exact_lots if row.get("direct_strict_evidence_rescue") == DIRECT_STRICT_EVIDENCE_RESCUE
    )
    report = {
        "schema_version": "exa-exact-lot-checkpoint-bridge-1.7",
        "status": "SUCCESS",
        "execution_status": "PASS",
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "domain": CLOTHING_INVENTORY,
        "market_code": market,
        "currency": MARKET_CURRENCIES[market],
        "source_mode": "EXA_EXACT_LOT_MULTIHOP",
        "query_pack": "SIX_MARKET_EXACT_LOT_CONTROLLED_COMMERCIAL_ANCHORS_V1",
        "queries_submitted": query_count,
        "hits_received": hit_count,
        "merged_candidates": len(candidates),
        "confirmed_sales": len(candidates),
        "strong_leads_requiring_verification": 0,
        "rejected_results": 0,
        "generic_pages_excluded": int(multihop.get("gateway_page_count") or 0),
        "direct_exact_lot_count": int(verification.get("exact_lot_candidate_count") or 0),
        "direct_strict_evidence_rescue_count": direct_rescue_count,
        "multihop_exact_lot_count": int(multihop.get("exact_lot_candidate_count") or 0),
        "strict_exact_lot_count": len(candidates),
        "source_native_value_evidence_count": sum(
            1
            for candidate in candidates
            if candidate.get("source_native_price_evidence_detected") is True
            and candidate.get("source_native_quantity_evidence_detected") is True
        ),
        "source_value_normalization_required_count": sum(
            1 for candidate in candidates if candidate.get("source_value_normalization_required") is True
        ),
        "currency_conversion_performed": False,
        "tax_calculation_performed": False,
        "customs_calculation_performed": False,
        "logistics_calculation_performed": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    result = {
        "search_run_report": report,
        "all_discovered_candidates": candidates,
        "discovery_top5": candidates[:5],
    }
    return apply_post_verification_top5_hard_gate(result)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_market(
    *, market: str, exa_api_key: str, output_dir: Path, results_per_query: int
) -> dict[str, Any]:
    primary_queries = MARKET_EXACT_LOT_QUERY_PACKS[market]
    recall_queries = MARKET_ZERO_YIELD_RECALL_QUERIES.get(market, ())
    anchor_queries = build_commercial_anchor_queries(
        market=market,
        project_domain=CLOTHING_INVENTORY,
        max_queries=MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET,
    )
    provider = ExaSearchProvider(exa_api_key)
    all_hits = []
    seen_urls: set[str] = set()
    query_rows: list[dict[str, Any]] = []

    def collect(
        query: str,
        *,
        stage: str,
        anchor_type: str = "",
        anchor_value: str = "",
    ) -> None:
        if not _market_anchored(query, market):
            raise RuntimeError(f"query not market anchored: {market}: {query}")
        if classify_project_domain(text=query) != CLOTHING_INVENTORY:
            raise RuntimeError(f"query escaped clothing domain: {market}: {query}")
        if "site:" in query.casefold():
            raise RuntimeError(f"source-specific query is forbidden: {market}: {query}")
        hits = list(provider.search(query, count=results_per_query))[:results_per_query]
        row = {
            "query": query,
            "query_stage": stage,
            "hits": [
                {"title": hit.title, "url": hit.url, "description": hit.description}
                for hit in hits
            ],
        }
        if stage == "COMMERCIAL_ANCHOR":
            row["commercial_anchor"] = {
                "type": _compact(anchor_type),
                "value": _compact(anchor_value),
                "qualification_evidence": False,
            }
        query_rows.append(row)
        for hit in hits:
            if hit.url in seen_urls:
                continue
            seen_urls.add(hit.url)
            all_hits.append(hit)

    def evaluate() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        benchmark = _custom_benchmark(
            market=market,
            query=" | ".join(row["query"] for row in query_rows),
            hits=all_hits,
            project_domain=CLOTHING_INVENTORY,
        )
        verification = verify_provider_unique_pages(
            benchmark,
            provider="exa",
            max_page_fetches=min(30, max(1, len(all_hits))),
        )
        multihop = resolve_exact_lot_multihop(
            verification,
            max_root_parents=6,
            max_navigation_depth=3,
            max_links_per_page=12,
            max_navigation_page_fetches=30,
        )
        return verification, multihop, _exact_lot_rows(verification, multihop)

    for query in primary_queries:
        collect(query, stage="PRIMARY")

    verification, multihop, exact_lots = evaluate()
    primary_strict_exact_lot_count = len(exact_lots)
    zero_yield_recall_triggered = not exact_lots and bool(recall_queries)

    if zero_yield_recall_triggered:
        for query in recall_queries:
            collect(query, stage="ZERO_YIELD_RECALL")
        verification, multihop, exact_lots = evaluate()

    post_recall_strict_exact_lot_count = len(exact_lots)
    anchor_pre_count = post_recall_strict_exact_lot_count
    anchor_pre_unique_hit_count = len(all_hits)
    anchor_min_unique_hit_count = _commercial_anchor_min_unique_discovery_hits(market)
    anchor_expansion_triggered = bool(
        anchor_queries
        and anchor_pre_count < COMMERCIAL_ANCHOR_THIN_YIELD_THRESHOLD
        and anchor_pre_unique_hit_count >= anchor_min_unique_hit_count
    )

    if anchor_expansion_triggered:
        for anchor in anchor_queries:
            collect(
                anchor["query"],
                stage="COMMERCIAL_ANCHOR",
                anchor_type=anchor["anchor_type"],
                anchor_value=anchor["anchor_value"],
            )
        verification, multihop, exact_lots = evaluate()

    result = build_checkpoint_result_from_exact_lots(
        exact_lots,
        market=market,
        query_count=len(query_rows),
        hit_count=sum(len(row["hits"]) for row in query_rows),
        verification=verification,
        multihop=multihop,
    )
    report = result["search_run_report"]
    report["primary_query_count"] = len(primary_queries)
    report["primary_strict_exact_lot_count"] = primary_strict_exact_lot_count
    report["zero_yield_recall_available"] = bool(recall_queries)
    report["zero_yield_recall_triggered"] = zero_yield_recall_triggered
    report["zero_yield_recall_query_count"] = len(recall_queries) if zero_yield_recall_triggered else 0
    report["zero_yield_recall_added_exact_lot_count"] = max(
        0, post_recall_strict_exact_lot_count - primary_strict_exact_lot_count
    )
    report["commercial_anchor_expansion_available"] = bool(anchor_queries)
    report["commercial_anchor_expansion_triggered"] = anchor_expansion_triggered
    report["commercial_anchor_trigger_threshold"] = COMMERCIAL_ANCHOR_THIN_YIELD_THRESHOLD
    report["commercial_anchor_min_unique_discovery_hits"] = anchor_min_unique_hit_count
    report["commercial_anchor_pre_unique_discovery_hit_count"] = anchor_pre_unique_hit_count
    report["commercial_anchor_query_count"] = len(anchor_queries) if anchor_expansion_triggered else 0
    report["commercial_anchor_pre_strict_exact_lot_count"] = anchor_pre_count
    report["commercial_anchor_added_exact_lot_count"] = max(0, len(exact_lots) - anchor_pre_count)
    report["commercial_anchor_is_qualification_evidence"] = False
    report["commercial_anchor_max_queries_per_market"] = MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET

    direct_rescue_urls = [
        row.get("url")
        for row in exact_lots
        if row.get("direct_strict_evidence_rescue") == DIRECT_STRICT_EVIDENCE_RESCUE
    ]
    _write_json(
        output_dir / "exa-exact-lot-resolution.json",
        {
            "schema_version": "exa-exact-lot-checkpoint-resolution-1.6",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "market": market,
            "project_domain": CLOTHING_INVENTORY,
            "provider": "exa",
            "queries": query_rows,
            "adaptive_zero_yield_recall": {
                "available": bool(recall_queries),
                "triggered": zero_yield_recall_triggered,
                "primary_strict_exact_lot_count": primary_strict_exact_lot_count,
                "recall_query_count": len(recall_queries) if zero_yield_recall_triggered else 0,
                "post_recall_strict_exact_lot_count": post_recall_strict_exact_lot_count,
            },
            "controlled_commercial_anchor_expansion": {
                "available": bool(anchor_queries),
                "triggered": anchor_expansion_triggered,
                "threshold": COMMERCIAL_ANCHOR_THIN_YIELD_THRESHOLD,
                "min_unique_discovery_hits": anchor_min_unique_hit_count,
                "pre_anchor_unique_discovery_hit_count": anchor_pre_unique_hit_count,
                "max_queries_per_market": MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET,
                "query_count": len(anchor_queries) if anchor_expansion_triggered else 0,
                "pre_anchor_strict_exact_lot_count": anchor_pre_count,
                "added_exact_lot_count": max(0, len(exact_lots) - anchor_pre_count),
                "final_strict_exact_lot_count": len(exact_lots),
                "anchor_is_qualification_evidence": False,
            },
            "direct_strict_evidence_rescue": {
                "rule": DIRECT_STRICT_EVIDENCE_RESCUE,
                "count": len(direct_rescue_urls),
                "urls": direct_rescue_urls,
                "brand_or_anchor_is_qualification_evidence": False,
            },
            "verification": verification,
            "multihop": multihop,
            "strict_exact_lot_count": len(exact_lots),
            "strict_exact_lot_urls": [row.get("url") for row in exact_lots],
            "source_native_value_evidence_count": report["source_native_value_evidence_count"],
            "source_value_normalization_required_count": report[
                "source_value_normalization_required_count"
            ],
            "production_mutation": False,
            "automatic_provider_activation": False,
        },
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", choices=tuple(MARKET_EXACT_LOT_QUERY_PACKS), required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--results-per-query", type=int, default=RESULTS_PER_QUERY)
    parser.add_argument("--persist-unified", action="store_true")
    parser.add_argument("--database-url", default="")
    parser.add_argument("--alembic-config", default="alembic.ini")
    args = parser.parse_args()

    if not 1 <= args.results_per_query <= RESULTS_PER_QUERY:
        raise SystemExit(f"--results-per-query must be between 1 and {RESULTS_PER_QUERY}")
    if args.persist_unified and not _compact(args.database_url):
        raise SystemExit("--database-url is required with --persist-unified")
    exa_api_key = _compact(os.environ.get("EXA_API_KEY"))
    if not exa_api_key:
        raise SystemExit("EXA_API_KEY is required")

    market = args.market.upper()
    output_dir = Path(args.output_dir)
    result = run_market(
        market=market,
        exa_api_key=exa_api_key,
        output_dir=output_dir,
        results_per_query=args.results_per_query,
    )
    paths = write_discovery_artifacts(result, output_dir)
    unified_path = write_unified_opportunity_report(
        result,
        output_dir,
        market_code=market,
        currency=MARKET_CURRENCIES[market],
        domain=CLOTHING_INVENTORY,
    )
    paths["unified_opportunity_report"] = unified_path

    if args.persist_unified:
        from opportunity_engine.persistence.live_unified_persistence import (
            persist_unified_report_with_artifacts,
        )

        _, persistence_summary_path = persist_unified_report_with_artifacts(
            unified_path,
            output_dir,
            database_url=args.database_url,
            config_path=args.alembic_config,
        )
        paths["unified_persistence_summary"] = persistence_summary_path

    report = result["search_run_report"]
    print(f"Status: {report['status']}")
    print(f"Market: {market}")
    print(f"Source: {report['source_mode']}")
    print(f"Queries: {report['queries_submitted']}")
    print(f"Hits: {report['hits_received']}")
    print(f"Strict Exact-Lots: {report['strict_exact_lot_count']}")
    print(f"Top opportunities: {report['top5_count']}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
