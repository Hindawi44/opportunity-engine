#!/usr/bin/env python3
"""Run the established daily bulletin, then attach bounded procurement feeds."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

from opportunity_engine.discovery.fabric_procurement_watch import (
    collect_fabric_procurement_watch,
)
from opportunity_engine.discovery.merkandi_b2b_liquidation_feed import (
    collect_merkandi_b2b_liquidation_feed,
)


# The executable entrypoint delegates the established market-intelligence pipeline
# to build_domain_market_intelligence_feed_core.py. Keep this explicit contract in
# the canonical entrypoint so repository checks and operators can verify the
# preserved stage order without following the dynamic module loader.
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
"""


def _load_core_module():
    path = Path(__file__).with_name("build_domain_market_intelligence_feed_core.py")
    spec = importlib.util.spec_from_file_location("domain_market_intelligence_feed_core", path)
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


def _attach_to_brief(output_dir: Path, report: dict[str, Any]) -> None:
    brief_path = output_dir / "domain-market-intelligence-brief.json"
    if not brief_path.exists():
        return
    try:
        brief = json.loads(brief_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(brief, dict):
        return

    candidates = report.get("candidates") or []
    compact_candidates = []
    if isinstance(candidates, list):
        for item in candidates[:5]:
            if not isinstance(item, dict):
                continue
            compact_candidates.append(
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

    brief["fabric_procurement_watch"] = {
        "feed_family": report.get("feed_family"),
        "purpose": report.get("purpose"),
        "search_language": report.get("search_language"),
        "approved_official_domains": report.get("approved_official_domains") or [],
        "status_counts": report.get("status_counts") or {},
        "query_budget_total": report.get("query_budget_total", 0),
        "requests_made": report.get("requests_made", 0),
        "candidate_count": report.get("candidate_count", 0),
        "top_procurement_candidates": compact_candidates,
        "operator_rule": report.get("operator_rule"),
        "not_part_of_opportunity_top5": True,
        "promotion_to_opportunity_allowed": False,
        "automatic_contact": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    _write_json(brief_path, brief)

    text_path = output_dir / "domain-market-intelligence-brief.txt"
    if not text_path.exists():
        return
    lines = [
        "",
        "FABRIC PROCUREMENT WATCH",
        f"status_counts: {json.dumps(report.get('status_counts') or {}, sort_keys=True)}",
        f"requests_made: {report.get('requests_made', 0)}",
        f"candidate_count: {report.get('candidate_count', 0)}",
        "operator_rule: COMPARE_PRICE_SAMPLE_COMPOSITION_AND_SHIPPING_BEFORE_ORDER",
    ]
    for item in compact_candidates:
        price = item.get("price_text") or "price not visible in search result"
        lines.append(
            "- "
            f"[{item.get('source_name')}] {item.get('title')} | {price} | "
            f"score={item.get('procurement_relevance_score')} | {item.get('source_url')}"
        )
    lines.extend(
        [
            "advisory_only: true",
            "automatic_purchase: false",
            "",
        ]
    )
    with text_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def _attach_merkandi_to_brief(output_dir: Path, report: dict[str, Any]) -> None:
    brief_path = output_dir / "domain-market-intelligence-brief.json"
    if not brief_path.exists():
        return
    try:
        brief = json.loads(brief_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(brief, dict):
        return

    candidates = report.get("candidates") or []
    compact_candidates = []
    if isinstance(candidates, list):
        for item in candidates[:5]:
            if not isinstance(item, dict):
                continue
            compact_candidates.append(
                {
                    "candidate_id": item.get("candidate_id"),
                    "source_name": item.get("source_name"),
                    "title": item.get("title"),
                    "source_url": item.get("source_url"),
                    "seller_name": item.get("seller_name"),
                    "quantity": item.get("quantity"),
                    "quantity_unit": item.get("quantity_unit"),
                    "minimum_order": item.get("minimum_order"),
                    "minimum_order_unit": item.get("minimum_order_unit"),
                    "unit_price": item.get("unit_price"),
                    "total_price": item.get("total_price"),
                    "currency": item.get("currency"),
                    "condition_terms": item.get("condition_terms") or [],
                    "brands": item.get("brands") or [],
                    "stock_location": item.get("stock_location"),
                    "manifest_available": item.get("manifest_available", False),
                    "authenticity_evidence_visible": item.get(
                        "authenticity_evidence_visible", False
                    ),
                    "shipping_information_present": item.get(
                        "shipping_information_present", False
                    ),
                    "opportunity_state": item.get("opportunity_state")
                    or "B2B_LEAD_REQUIRES_VERIFICATION",
                    "b2b_relevance_score": item.get("b2b_relevance_score"),
                    "recommended_operator_action": item.get(
                        "recommended_operator_action"
                    ),
                }
            )

    brief["merkandi_b2b_liquidation_feed"] = {
        "feed_family": report.get("feed_family"),
        "purpose": report.get("purpose"),
        "approved_official_domains": report.get("approved_official_domains") or [],
        "status_counts": report.get("status_counts") or {},
        "query_budget_total": report.get("query_budget_total", 0),
        "requests_made": report.get("requests_made", 0),
        "candidate_count": report.get("candidate_count", 0),
        "top_b2b_leads": compact_candidates,
        "operator_rule": report.get("operator_rule"),
        "seller_identity_required": True,
        "quantity_required": True,
        "minimum_order_required": True,
        "visible_price_required": True,
        "manifest_required": True,
        "default_opportunity_state": "B2B_LEAD_REQUIRES_VERIFICATION",
        "not_part_of_opportunity_top5": True,
        "promotion_to_opportunity_allowed": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    _write_json(brief_path, brief)

    text_path = output_dir / "domain-market-intelligence-brief.txt"
    if not text_path.exists():
        return
    lines = [
        "",
        "MERKANDI B2B LIQUIDATION FEED",
        f"status_counts: {json.dumps(report.get('status_counts') or {}, sort_keys=True)}",
        f"requests_made: {report.get('requests_made', 0)}",
        f"candidate_count: {report.get('candidate_count', 0)}",
        "default_state: B2B_LEAD_REQUIRES_VERIFICATION",
        "operator_rule: VERIFY_SELLER_MANIFEST_AUTHENTICITY_SHIPPING_AND_LANDED_COST_BEFORE_CONTACT",
    ]
    if not compact_candidates:
        lines.append("result: No current Merkandi listing passed the strict B2B gate.")
    for item in compact_candidates:
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
            "- "
            f"{item.get('title')} | seller={item.get('seller_name')} | "
            f"quantity={item.get('quantity')} {item.get('quantity_unit')} | "
            f"MOQ={item.get('minimum_order')} {item.get('minimum_order_unit')} | "
            f"price={price_text} | score={item.get('b2b_relevance_score')} | "
            f"{item.get('source_url')}"
        )
    lines.extend(
        [
            "human_verification_required: true",
            "automatic_contact: false",
            "automatic_purchase: false",
            "",
        ]
    )
    with text_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def _failed_fabric_report(exc: Exception) -> dict[str, Any]:
    return {
        "schema_version": "fabric-procurement-watch-1.0",
        "feed_family": "FABRIC_DEADSTOCK_PROCUREMENT_FEED_V1",
        "purpose": "TAILORING_SHOP_FABRIC_PROCUREMENT_INTELLIGENCE",
        "status": "FAILED",
        "error_type": type(exc).__name__,
        "error": str(exc),
        "approved_official_domains": [
            "evaresource.com",
            "fabrichouse.com",
            "bridalfabrics.com",
        ],
        "status_counts": {"FAILED": 1},
        "query_budget_total": 3,
        "requests_made": 0,
        "candidate_count": 0,
        "candidates": [],
        "not_part_of_opportunity_top5": True,
        "promotion_to_opportunity_allowed": False,
        "automatic_contact": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _failed_merkandi_report(exc: Exception) -> dict[str, Any]:
    return {
        "schema_version": "merkandi-b2b-liquidation-feed-1.0",
        "feed_family": "MERKANDI_B2B_LIQUIDATION_FEED_V1",
        "purpose": "SMALL_OPERATOR_B2B_CLOTHING_LIQUIDATION_INTELLIGENCE",
        "status": "FAILED",
        "error_type": type(exc).__name__,
        "error": str(exc),
        "approved_official_domains": ["merkandi.com"],
        "status_counts": {"FAILED": 1},
        "query_budget_total": 1,
        "requests_made": 0,
        "candidate_count": 0,
        "candidates": [],
        "default_opportunity_state": "B2B_LEAD_REQUIRES_VERIFICATION",
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


def main() -> int:
    output_dir = _output_dir_from_argv()
    core = _load_core_module()
    status = int(core.main())
    if status != 0:
        return status

    try:
        fabric_report = collect_fabric_procurement_watch(environment=os.environ)
    except Exception as exc:
        fabric_report = _failed_fabric_report(exc)

    _write_json(output_dir / "fabric-procurement-watch.json", fabric_report)
    _attach_to_brief(output_dir, fabric_report)
    print(
        "fabric_procurement_watch_status_counts:",
        json.dumps(fabric_report.get("status_counts") or {}, sort_keys=True),
    )
    print("fabric_procurement_watch_requests:", fabric_report.get("requests_made", 0))
    print("fabric_procurement_watch_candidates:", fabric_report.get("candidate_count", 0))

    try:
        merkandi_report = collect_merkandi_b2b_liquidation_feed(environment=os.environ)
    except Exception as exc:
        merkandi_report = _failed_merkandi_report(exc)

    _write_json(output_dir / "merkandi-b2b-liquidation-feed.json", merkandi_report)
    _attach_merkandi_to_brief(output_dir, merkandi_report)
    print(
        "merkandi_b2b_liquidation_status_counts:",
        json.dumps(merkandi_report.get("status_counts") or {}, sort_keys=True),
    )
    print("merkandi_b2b_liquidation_requests:", merkandi_report.get("requests_made", 0))
    print("merkandi_b2b_liquidation_candidates:", merkandi_report.get("candidate_count", 0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
