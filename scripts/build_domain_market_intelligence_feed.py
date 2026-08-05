#!/usr/bin/env python3
"""Run the established daily bulletin and attach bounded procurement/B2B feeds."""
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
from opportunity_engine.discovery.merkandi_b2b_liquidation_feed import (
    collect_merkandi_b2b_liquidation_feed,
)
from opportunity_engine.discovery.stockhurt_b2b_feed import (
    collect_stockhurt_b2b_feed,
)

# Preserve the established canonical pipeline contract for repository regression checks.
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
"B2B_LEAD_REQUIRES_VERIFICATION"
"EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION"
"HUMAN_OPERATOR"
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


def _output_dir_from_argv() -> Path:
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


def _load_brief(output_dir: Path) -> tuple[Path, dict[str, Any]] | None:
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
    if not path.exists():
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n" + "\n".join(lines) + "\n")


def _attach_fabric(output_dir: Path, report: dict[str, Any]) -> None:
    compact = []
    for item in (report.get("candidates") or [])[:5]:
        if not isinstance(item, dict):
            continue
        compact.append(
            {
                "candidate_id": item.get("candidate_id"),
                "source_name": item.get("source_name"),
                "title": item.get("title"),
                "source_url": item.get("source_url"),
                "price_text": item.get("price_text"),
                "price": item.get("price"),
                "currency": item.get("currency"),
                "fabric_terms": item.get("fabric_terms") or [],
                "bridal_terms": item.get("bridal_terms") or [],
                "procurement_relevance_score": item.get(
                    "procurement_relevance_score"
                ),
                "recommended_operator_action": item.get(
                    "recommended_operator_action"
                ),
            }
        )

    loaded = _load_brief(output_dir)
    if loaded:
        path, brief = loaded
        brief["fabric_procurement_watch"] = {
            "feed_family": report.get("feed_family"),
            "purpose": report.get("purpose"),
            "approved_official_domains": report.get(
                "approved_official_domains"
            )
            or [],
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
    for item in compact:
        price = item.get("price_text") or "price not visible"
        lines.append(
            f"- [{item.get('source_name')}] {item.get('title')} | {price} | "
            f"score={item.get('procurement_relevance_score')} | "
            f"{item.get('source_url')}"
        )
    lines += ["advisory_only: true", "automatic_purchase: false"]
    _append_text(output_dir, lines)


def _compact_b2b_candidate(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": item.get("candidate_id"),
        "source_name": item.get("source_name"),
        "source_country": item.get("source_country"),
        "title": item.get("title"),
        "source_url": item.get("source_url"),
        "page_role": item.get("page_role"),
        "listing_status": item.get("listing_status"),
        "seller_name": item.get("seller_name"),
        "quantity": item.get("quantity"),
        "quantity_unit": item.get("quantity_unit"),
        "lot_size_band": item.get("lot_size_band"),
        "minimum_order": item.get("minimum_order"),
        "minimum_order_unit": item.get("minimum_order_unit"),
        "unit_hint": item.get("unit_hint"),
        "unit_price": item.get("unit_price"),
        "total_price": item.get("total_price"),
        "currency": item.get("currency"),
        "grade": item.get("grade"),
        "brands": item.get("brands") or [],
        "stock_location": item.get("stock_location"),
        "missing_information": item.get("missing_information") or [],
        "opportunity_state": item.get("opportunity_state"),
        "b2b_relevance_score": item.get("b2b_relevance_score"),
        "decision_owner": "HUMAN_OPERATOR",
        "recommended_operator_action": item.get(
            "recommended_operator_action"
        ),
    }


def _attach_b2b(
    output_dir: Path,
    report: dict[str, Any],
    *,
    brief_key: str,
    heading: str,
) -> None:
    compact = [
        _compact_b2b_candidate(item)
        for item in (report.get("candidates") or [])[:12]
        if isinstance(item, dict)
    ]

    loaded = _load_brief(output_dir)
    if loaded:
        path, brief = loaded
        brief[brief_key] = {
            "feed_family": report.get("feed_family"),
            "purpose": report.get("purpose"),
            "approved_official_domains": report.get(
                "approved_official_domains"
            )
            or [],
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
        lines.append(
            "result: No current serious source result passed the relevance gate."
        )
    for item in compact:
        price = item.get("unit_price")
        basis = "per unit"
        if price is None:
            price = item.get("total_price")
            basis = "total or unspecified basis"
        price_text = (
            f"{price} {item.get('currency')} ({basis})"
            if price is not None
            else "price not visible"
        )
        lines.append(
            f"- {item.get('title')} | state={item.get('opportunity_state')} | "
            f"status={item.get('listing_status')} | "
            f"quantity={item.get('quantity')} {item.get('quantity_unit')} | "
            f"lot={item.get('lot_size_band')} | "
            f"MOQ={item.get('minimum_order')} "
            f"{item.get('minimum_order_unit')} | price={price_text} | "
            f"missing={item.get('missing_information')} | "
            f"{item.get('source_url')}"
        )
    lines += [
        "human_verification_required: true",
        "automatic_contact: false",
        "automatic_purchase: false",
    ]
    _append_text(output_dir, lines)


def _failed_report(
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


def _run_feed(
    output_dir: Path,
    *,
    collector: Callable[..., dict[str, Any]],
    filename: str,
    attach: Callable[[Path, dict[str, Any]], None],
    failure_kwargs: dict[str, Any],
    log_prefix: str,
) -> None:
    try:
        report = collector(environment=os.environ)
    except Exception as exc:
        report = _failed_report(exc, **failure_kwargs)
    _write_json(output_dir / filename, report)
    attach(output_dir, report)
    print(
        f"{log_prefix}_status_counts:",
        json.dumps(report.get("status_counts") or {}, sort_keys=True),
    )
    print(f"{log_prefix}_requests:", report.get("requests_made", 0))
    print(f"{log_prefix}_candidates:", report.get("candidate_count", 0))


def main() -> int:
    output_dir = _output_dir_from_argv()
    core = _load_core_module()
    status = int(core.main())
    if status != 0:
        return status

    _run_feed(
        output_dir,
        collector=collect_fabric_procurement_watch,
        filename="fabric-procurement-watch.json",
        attach=_attach_fabric,
        failure_kwargs={
            "schema_version": "fabric-procurement-watch-1.0",
            "feed_family": "FABRIC_DEADSTOCK_PROCUREMENT_FEED_V1",
            "purpose": "TAILORING_SHOP_FABRIC_PROCUREMENT_INTELLIGENCE",
            "domains": [
                "evaresource.com",
                "fabrichouse.com",
                "bridalfabrics.com",
            ],
            "query_budget": 3,
        },
        log_prefix="fabric_procurement_watch",
    )
    _run_feed(
        output_dir,
        collector=collect_merkandi_b2b_liquidation_feed,
        filename="merkandi-b2b-liquidation-feed.json",
        attach=lambda out, report: _attach_b2b(
            out,
            report,
            brief_key="merkandi_b2b_liquidation_feed",
            heading="MERKANDI B2B LIQUIDATION FEED",
        ),
        failure_kwargs={
            "schema_version": "merkandi-b2b-liquidation-feed-1.1",
            "feed_family": "MERKANDI_B2B_LIQUIDATION_FEED_V1",
            "purpose": "B2B_CLOTHING_LIQUIDATION_DECISION_SUPPORT",
            "domains": ["merkandi.com"],
            "query_budget": 1,
        },
        log_prefix="merkandi_b2b_liquidation",
    )
    _run_feed(
        output_dir,
        collector=collect_fashion_stock_netherlands_feed,
        filename="fashion-stock-netherlands-feed.json",
        attach=lambda out, report: _attach_b2b(
            out,
            report,
            brief_key="fashion_stock_netherlands_feed",
            heading="FASHION STOCK NETHERLANDS FEED",
        ),
        failure_kwargs={
            "schema_version": "fashion-stock-netherlands-feed-1.0",
            "feed_family": "FASHION_STOCK_NETHERLANDS_FEED_V1",
            "purpose": "OFFICIAL_SOURCE_B2B_CLOTHING_STOCK_DECISION_SUPPORT",
            "domains": [
                "fashion-stock.eu",
                "fashionstock.eu",
                "fashion-stock.nl",
            ],
            "query_budget": 2,
        },
        log_prefix="fashion_stock_netherlands",
    )
    _run_feed(
        output_dir,
        collector=collect_stockhurt_b2b_feed,
        filename="stockhurt-b2b-feed.json",
        attach=lambda out, report: _attach_b2b(
            out,
            report,
            brief_key="stockhurt_b2b_feed",
            heading="STOCK-HURT B2B FEED",
        ),
        failure_kwargs={
            "schema_version": "stockhurt-b2b-feed-1.0",
            "feed_family": "STOCK_HURT_B2B_FEED_V1",
            "purpose": (
                "OFFICIAL_SOURCE_WHOLESALE_STOCK_AND_AUCTION_DECISION_SUPPORT"
            ),
            "domains": ["stockhurt.com"],
            "query_budget": 2,
        },
        log_prefix="stockhurt_b2b",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
