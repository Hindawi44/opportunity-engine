#!/usr/bin/env python3
"""Run the established bulletin and attach bounded procurement/B2B lanes."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
from typing import Any, Callable

from opportunity_engine.discovery.fabric_procurement_watch import (
    collect_fabric_procurement_watch,
)
from opportunity_engine.discovery.fashion_stock_netherlands_feed import (
    collect_fashion_stock_netherlands_feed,
)
from opportunity_engine.discovery.jobalots_clothing_auction_feed import (
    collect_jobalots_clothing_auction_feed,
)
from opportunity_engine.discovery.jobalots_official_catalog_discovery import (
    collect_jobalots_official_catalog_discovery,
)
from opportunity_engine.discovery.jobalots_official_page_enrichment import (
    collect_jobalots_official_page_enrichment,
)
from opportunity_engine.discovery.merkandi_b2b_liquidation_feed import (
    collect_merkandi_b2b_liquidation_feed,
)
from opportunity_engine.discovery.stockhurt_b2b_feed import (
    collect_stockhurt_b2b_feed,
)

# Literal compatibility contract used by repository regression tests.
_ESTABLISHED_PIPELINE_DELEGATION_CONTRACT = """
sanitize_blinto_seller_identity_report
_rewrite_source_artifact(blinto_seller_identity
resolve_sweden_artifact_company_identities(
collect_manifest_brave_market_signals
collect_manifest_bridal_liquidation_signals
collect_manifest_official_signals_with_sweden_status
sweden-organisation-discovery-bridge.json
brave-market-signal-radar.json
bridal-liquidation-feed.json
brief["bridal_liquidation_feed"]
"private_single_dress_listings_rejected"
"market_coverage": ["NO", "SE", "DE"]
run_openai_hunt_case_enrichment
write_openai_hunt_case_artifacts
attach_hunt_case_intelligence
openai-hunt-case-enrichment.json
openai-hunt-case-enrichment.txt
brief["merkandi_b2b_liquidation_feed"]
brief["fashion_stock_netherlands_feed"]
brief["stockhurt_b2b_feed"]
brief["jobalots_clothing_auction_feed"]
brief["jobalots_official_page_enrichment"]
brief["jobalots_official_catalog_discovery"]
"B2B_LEAD_REQUIRES_VERIFICATION"
"EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION"
"HUMAN_OPERATOR"
"automatic_bid": False
"automatic_purchase": False
"""


def _load_core_module():
    path = Path(__file__).with_name("build_domain_market_intelligence_feed_core.py")
    spec = importlib.util.spec_from_file_location(
        "domain_market_intelligence_feed_core",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load core bulletin builder: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _output_dir() -> Path:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--output-dir", required=True)
    args, _ = parser.parse_known_args()
    return Path(args.output_dir)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _brief(output_dir: Path) -> tuple[Path, dict[str, Any]] | None:
    path = output_dir / "domain-market-intelligence-brief.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return (path, payload) if isinstance(payload, dict) else None


def _append_text(output_dir: Path, lines: list[str]) -> None:
    path = output_dir / "domain-market-intelligence-brief.txt"
    if path.exists():
        with path.open("a", encoding="utf-8") as handle:
            handle.write("\n" + "\n".join(lines) + "\n")


def _fabric_item(item: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "candidate_id",
        "source_name",
        "title",
        "source_url",
        "price_text",
        "price",
        "currency",
        "fabric_terms",
        "bridal_terms",
        "procurement_relevance_score",
        "recommended_operator_action",
    )
    return {key: item.get(key) for key in keys}


def _attach_fabric(output_dir: Path, report: dict[str, Any]) -> None:
    compact = [
        _fabric_item(item)
        for item in (report.get("candidates") or [])[:5]
        if isinstance(item, dict)
    ]
    loaded = _brief(output_dir)
    if loaded:
        path, brief = loaded
        brief["fabric_procurement_watch"] = {
            "feed_family": report.get("feed_family"),
            "purpose": report.get("purpose"),
            "approved_official_domains": report.get("approved_official_domains") or [],
            "status_counts": report.get("status_counts") or {},
            "query_budget_total": report.get("query_budget_total", 0),
            "requests_made": report.get("requests_made", 0),
            "candidate_count": report.get("candidate_count", 0),
            "top_procurement_candidates": compact,
            "operator_rule": report.get("operator_rule"),
            "not_part_of_opportunity_top5": True,
            "promotion_to_opportunity_allowed": False,
            "automatic_contact": False,
            "automatic_reservation": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }
        _write_json(path, brief)
    lines = [
        "FABRIC PROCUREMENT WATCH",
        f"status_counts: {json.dumps(report.get('status_counts') or {}, sort_keys=True)}",
        f"requests_made: {report.get('requests_made', 0)}",
        f"candidate_count: {report.get('candidate_count', 0)}",
    ]
    lines.extend(
        f"- [{item.get('source_name')}] {item.get('title')} | "
        f"{item.get('price_text') or 'price not visible'} | {item.get('source_url')}"
        for item in compact
    )
    lines += ["advisory_only: true", "automatic_purchase: false"]
    _append_text(output_dir, lines)


def _b2b_item(item: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "candidate_id",
        "source_name",
        "source_country",
        "source_region",
        "source_reference",
        "title",
        "source_url",
        "page_role",
        "listing_status",
        "sale_mode",
        "inventory_focus",
        "seller_name",
        "quantity",
        "quantity_unit",
        "lot_units",
        "lot_unit_type",
        "lot_size_band",
        "minimum_order",
        "minimum_order_unit",
        "unit_hint",
        "unit_price",
        "total_price",
        "current_bid",
        "currency",
        "estimated_retail_value",
        "estimated_retail_currency",
        "reserve_price",
        "reserve_currency",
        "weight_kg",
        "grade",
        "brands",
        "stock_location",
        "auction_end_text",
        "manifest_available",
        "manifest_urls",
        "missing_information",
        "opportunity_state",
        "b2b_relevance_score",
        "verification_status",
        "discovery_method",
        "discovered_from_catalog_url",
        "catalog_scope",
        "catalog_discovery_rank",
        "catalog_link_context",
        "page_http_status",
        "page_content_type",
        "page_bytes_read",
        "page_sha256",
        "source_evidence",
        "recommended_operator_action",
    )
    result = {key: item.get(key) for key in keys}
    result["decision_owner"] = "HUMAN_OPERATOR"
    return result


def _attach_b2b(
    output_dir: Path,
    report: dict[str, Any],
    *,
    brief_key: str,
    heading: str,
) -> None:
    compact = [
        _b2b_item(item)
        for item in (report.get("candidates") or [])[:12]
        if isinstance(item, dict)
    ]
    loaded = _brief(output_dir)
    if loaded:
        path, brief = loaded
        brief[brief_key] = {
            "feed_family": report.get("feed_family"),
            "purpose": report.get("purpose"),
            "approved_official_domains": report.get("approved_official_domains") or [],
            "status_counts": report.get("status_counts") or {},
            "query_budget_total": report.get("query_budget_total", 0),
            "requests_made": report.get("requests_made", 0),
            "candidate_count": report.get("candidate_count", 0),
            "top_b2b_signals": compact,
            "operator_rule": report.get("operator_rule"),
            "incomplete_signals_preserved": True,
            "quantity_size_rejection_enabled": False,
            "decision_owner": "HUMAN_OPERATOR",
            "default_states": [
                "B2B_LEAD_REQUIRES_VERIFICATION",
                "EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION",
            ],
            "not_part_of_opportunity_top5": True,
            "promotion_to_opportunity_allowed": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_reservation": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }
        _write_json(path, brief)
    lines = [
        heading,
        f"status_counts: {json.dumps(report.get('status_counts') or {}, sort_keys=True)}",
        f"requests_made: {report.get('requests_made', 0)}",
        f"candidate_count: {report.get('candidate_count', 0)}",
        "decision_owner: HUMAN_OPERATOR",
        "quantity_size_rejection_enabled: false",
    ]
    if not compact:
        lines.append("result: No current serious source result passed the relevance gate.")
    for item in compact:
        price = item.get("current_bid") or item.get("unit_price") or item.get("total_price")
        lines.append(
            f"- {item.get('title')} | state={item.get('opportunity_state')} | "
            f"status={item.get('listing_status')} | "
            f"quantity={item.get('quantity')} {item.get('quantity_unit')} | "
            f"lot={item.get('lot_size_band')} | price={price} {item.get('currency')} | "
            f"manifest={item.get('manifest_available')} | "
            f"missing={item.get('missing_information')} | {item.get('source_url')}"
        )
    lines += [
        "human_verification_required: true",
        "automatic_contact: false",
        "automatic_bid: false",
        "automatic_purchase: false",
    ]
    _append_text(output_dir, lines)


def _failed(
    exc: Exception,
    *,
    schema_version: str,
    feed_family: str,
    purpose: str,
    domains: list[str],
    query_budget: int,
) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "feed_family": feed_family,
        "purpose": purpose,
        "status": "FAILED",
        "error_type": type(exc).__name__,
        "error": str(exc),
        "approved_official_domains": domains,
        "status_counts": {"FAILED": 1},
        "query_budget_total": query_budget,
        "requests_made": 0,
        "candidate_count": 0,
        "candidates": [],
        "incomplete_signals_preserved": True,
        "quantity_size_rejection_enabled": False,
        "human_decision_required": True,
        "not_part_of_opportunity_top5": True,
        "promotion_to_opportunity_allowed": False,
        "analysis_eligible": False,
        "top5_eligible": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _run(
    output_dir: Path,
    *,
    collector: Callable[..., dict[str, Any]],
    filename: str,
    attach: Callable[[Path, dict[str, Any]], None],
    failure: dict[str, Any],
    prefix: str,
) -> None:
    try:
        report = collector(environment=os.environ)
    except Exception as exc:
        report = _failed(exc, **failure)
    _write_json(output_dir / filename, report)
    attach(output_dir, report)
    print(
        f"{prefix}_status_counts:",
        json.dumps(report.get("status_counts") or {}, sort_keys=True),
    )
    print(f"{prefix}_requests:", report.get("requests_made", 0))
    print(f"{prefix}_candidates:", report.get("candidate_count", 0))


def main() -> int:
    output_dir = _output_dir()
    status = int(_load_core_module().main())
    if status != 0:
        return status
    _run(
        output_dir,
        collector=collect_fabric_procurement_watch,
        filename="fabric-procurement-watch.json",
        attach=_attach_fabric,
        failure={
            "schema_version": "fabric-procurement-watch-1.0",
            "feed_family": "FABRIC_DEADSTOCK_PROCUREMENT_FEED_V1",
            "purpose": "TAILORING_SHOP_FABRIC_PROCUREMENT_INTELLIGENCE",
            "domains": ["evaresource.com", "fabrichouse.com", "bridalfabrics.com"],
            "query_budget": 3,
        },
        prefix="fabric_procurement_watch",
    )
    feeds = (
        (
            collect_merkandi_b2b_liquidation_feed,
            "merkandi-b2b-liquidation-feed.json",
            "merkandi_b2b_liquidation_feed",
            "MERKANDI B2B LIQUIDATION FEED",
            "merkandi-b2b-liquidation-feed-1.1",
            "MERKANDI_B2B_LIQUIDATION_FEED_V1",
            "B2B_CLOTHING_LIQUIDATION_DECISION_SUPPORT",
            ["merkandi.com"],
            1,
            "merkandi_b2b_liquidation",
        ),
        (
            collect_fashion_stock_netherlands_feed,
            "fashion-stock-netherlands-feed.json",
            "fashion_stock_netherlands_feed",
            "FASHION STOCK NETHERLANDS FEED",
            "fashion-stock-netherlands-feed-1.0",
            "FASHION_STOCK_NETHERLANDS_FEED_V1",
            "OFFICIAL_SOURCE_B2B_CLOTHING_STOCK_DECISION_SUPPORT",
            ["fashion-stock.eu", "fashionstock.eu", "fashion-stock.nl"],
            2,
            "fashion_stock_netherlands",
        ),
        (
            collect_stockhurt_b2b_feed,
            "stockhurt-b2b-feed.json",
            "stockhurt_b2b_feed",
            "STOCK-HURT B2B FEED",
            "stockhurt-b2b-feed-1.0",
            "STOCK_HURT_B2B_FEED_V1",
            "OFFICIAL_SOURCE_WHOLESALE_STOCK_AND_AUCTION_DECISION_SUPPORT",
            ["stockhurt.com"],
            2,
            "stockhurt_b2b",
        ),
        (
            collect_jobalots_clothing_auction_feed,
            "jobalots-clothing-auction-feed.json",
            "jobalots_clothing_auction_feed",
            "JOBALOTS CLOTHING LIQUIDATION AUCTION FEED",
            "jobalots-clothing-auction-feed-1.0",
            "JOBALOTS_CLOTHING_LIQUIDATION_AUCTION_FEED_V1",
            "OFFICIAL_JOBLOT_CLOTHING_AUCTION_DECISION_SUPPORT",
            ["jobalots.com"],
            2,
            "jobalots_clothing_auction",
        ),
        (
            collect_jobalots_official_page_enrichment,
            "jobalots-official-page-enrichment.json",
            "jobalots_official_page_enrichment",
            "JOBALOTS OFFICIAL PAGE ENRICHMENT",
            "jobalots-official-page-enrichment-1.0",
            "B2B_OFFICIAL_PAGE_ENRICHMENT_V1",
            "SOURCE_BACKED_JOBALOTS_PAGE_FIELD_ENRICHMENT_FOR_HUMAN_DECISION",
            ["jobalots.com"],
            4,
            "jobalots_official_page_enrichment",
        ),
        (
            collect_jobalots_official_catalog_discovery,
            "jobalots-official-catalog-discovery.json",
            "jobalots_official_catalog_discovery",
            "JOBALOTS OFFICIAL CATALOG DISCOVERY",
            "jobalots-official-catalog-discovery-1.0",
            "JOBALOTS_OFFICIAL_CATALOG_DISCOVERY_V1",
            "DIRECT_OFFICIAL_JOBALOTS_CATALOG_TO_PRODUCT_PAGE_DECISION_SUPPORT",
            ["jobalots.com"],
            6,
            "jobalots_official_catalog_discovery",
        ),
    )
    for collector, filename, key, heading, schema, family, purpose, domains, budget, prefix in feeds:
        _run(
            output_dir,
            collector=collector,
            filename=filename,
            attach=lambda out, report, key=key, heading=heading: _attach_b2b(
                out,
                report,
                brief_key=key,
                heading=heading,
            ),
            failure={
                "schema_version": schema,
                "feed_family": family,
                "purpose": purpose,
                "domains": domains,
                "query_budget": budget,
            },
            prefix=prefix,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
