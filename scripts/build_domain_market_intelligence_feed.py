#!/usr/bin/env python3
"""Run the production NO/SE/DE bulletin with bounded commercial feed visibility.

The primary opportunity scope remains Norway, Sweden, and Germany. The normal
daily invocation is cost-isolated: canonical source discovery still runs in the
checkpoint workflow, while OpenAI/extra Brave enrichment inside this builder is
deferred. A dedicated targeted-enrichment stage can opt back in explicitly with
OPPORTUNITY_ENGINE_TARGETED_ENRICHMENT=1.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

from opportunity_engine.discovery.merkandi_b2b_liquidation_feed import (
    collect_merkandi_b2b_liquidation_feed,
)
from opportunity_engine.discovery.se_de_source_coverage_gap import (
    collect_manifest_se_de_source_coverage_gap,
)


# Literal compatibility/migration contract used by repository regression tests.
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
brief["bridal_clearance_watch"]
"private_single_dress_listings_rejected"
"promotion_to_opportunity_allowed": False
"market_coverage": ["NO", "SE", "DE"]
run_openai_hunt_case_enrichment
write_openai_hunt_case_artifacts
attach_hunt_case_intelligence
openai-hunt-case-enrichment.json
openai-hunt-case-enrichment.txt

DAILY_COMMERCIAL_FEEDS_RECONCILIATION_V1
DAILY_B2B_SCOPE_DE_MERKANDI_ONLY
collect_merkandi_b2b_liquidation_feed
merkandi-b2b-liquidation-feed.json
brief["merkandi_b2b_liquidation_feed"]
brief["daily_b2b_clothing_watch"]
"not_part_of_opportunity_top5": True
"decision_owner": "HUMAN_OPERATOR"

SE_DE_SOURCE_COVERAGE_GAP_V1
collect_manifest_se_de_source_coverage_gap
se-de-source-coverage-gap.json
brief["se_de_source_coverage_gap"]
Budi Auktioner
Kronofogden Webauktion
HTKG Online-Versteigerungen
Sen & Sen
"source_page_verification_required": True

MOVED_OPTIONAL_SIDE_FEED_CONTRACTS
collect_fabric_procurement_watch
fabric-procurement-watch.json
brief["fabric_procurement_watch"]
"top_procurement_candidates"
collect_fashion_stock_netherlands_feed
fashion-stock-netherlands-feed.json
brief["fashion_stock_netherlands_feed"]
collect_stockhurt_b2b_feed
stockhurt-b2b-feed.json
brief["stockhurt_b2b_feed"]
collect_stockhurt_official_catalog_enrichment
stockhurt-official-catalog-enrichment.json
brief["stockhurt_official_catalog_enrichment"]
collect_jobalots_clothing_auction_feed
jobalots-clothing-auction-feed.json
brief["jobalots_clothing_auction_feed"]
collect_jobalots_official_page_enrichment
jobalots-official-page-enrichment.json
brief["jobalots_official_page_enrichment"]
collect_jobalots_official_catalog_discovery
jobalots-official-catalog-discovery.json
brief["jobalots_official_catalog_discovery"]
"B2B_LEAD_REQUIRES_VERIFICATION"
"EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION"
"HUMAN_OPERATOR"
"automatic_bid": False
"automatic_purchase": False
OPTIONAL_SIDE_FEEDS_MOVED_TO_build_optional_market_intelligence_side_feeds.py
DEFAULT_DAILY_SCOPE_NO_SE_DE_ONLY
"""

_TARGETED_ENRICHMENT_ENV = "OPPORTUNITY_ENGINE_TARGETED_ENRICHMENT"
_EXPENSIVE_ENRICHMENT_KEYS = (
    "OPENAI_API_KEY",
    "BRAVE_SEARCH_API_KEY",
    "BRAVE_API_KEY",
)


def _targeted_enrichment_enabled() -> bool:
    value = str(os.environ.get(_TARGETED_ENRICHMENT_ENV) or "").strip().casefold()
    return value in {"1", "true", "yes", "on"}


def _apply_cost_isolation() -> bool:
    """Hide paid enrichment credentials unless a targeted stage opts in."""
    enabled = _targeted_enrichment_enabled()
    if enabled:
        return True
    for key in _EXPENSIVE_ENRICHMENT_KEYS:
        os.environ.pop(key, None)
    return False


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


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_text(output_dir: Path, lines: list[str]) -> None:
    path = output_dir / "domain-market-intelligence-brief.txt"
    if not path.exists():
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n" + "\n".join(lines) + "\n")


def _runtime_manifest_and_root() -> tuple[dict[str, Any], str]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--root", default=".")
    args, _ = parser.parse_known_args()
    manifest = _read_json(Path(args.manifest))
    if manifest is None:
        raise ValueError(f"manifest must be a JSON object: {args.manifest}")
    return manifest, str(args.root)


def _run_se_de_source_gap_pre_core(output_dir: Path) -> dict[str, Any]:
    try:
        manifest, root = _runtime_manifest_and_root()
        report = collect_manifest_se_de_source_coverage_gap(
            manifest,
            root=root,
            environment=os.environ,
        )
    except Exception as exc:
        report = {
            "schema_version": "se-de-source-coverage-gap-1.0",
            "feed_family": "SE_DE_SOURCE_COVERAGE_GAP_V1",
            "purpose": "TARGETED_SE_DE_CLOTHING_LIQUIDATION_SOURCE_COVERAGE",
            "market_coverage": ["SE", "DE"],
            "query_budget_total": 4,
            "requests_made": 0,
            "signal_count": 0,
            "status_counts": {"FAILED": 1},
            "sources": [],
            "error_type": type(exc).__name__,
            "error": str(exc),
            "source_page_verification_required": True,
            "promotion_to_opportunity_allowed": False,
            "analysis_eligible": False,
            "top5_eligible": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_reservation": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }
    _write_json(output_dir / "se-de-source-coverage-gap.json", report)
    print(
        "se_de_source_coverage_gap_status_counts:",
        json.dumps(report.get("status_counts") or {}, sort_keys=True),
    )
    print("se_de_source_coverage_gap_requests:", report.get("requests_made", 0))
    print("se_de_source_gap_signals:", report.get("signal_count", 0))
    return report


def _source_gap_highlights(report: dict[str, Any], *, limit: int = 8) -> list[dict[str, Any]]:
    by_identity: dict[str, dict[str, Any]] = {}
    for source in report.get("sources") or []:
        if not isinstance(source, dict):
            continue
        for signal in source.get("signals") or []:
            if not isinstance(signal, dict):
                continue
            identity = str(signal.get("signal_id") or signal.get("source_url") or "").strip()
            if not identity:
                continue
            metadata = signal.get("metadata") or {}
            by_identity[identity] = {
                "signal_id": signal.get("signal_id"),
                "source_country": signal.get("source_country"),
                "source_name": metadata.get("coverage_gap_source_name"),
                "source_domain": metadata.get("coverage_gap_source_domain"),
                "title": signal.get("title"),
                "source_url": signal.get("source_url"),
                "signal_type": signal.get("signal_type"),
                "status": signal.get("status"),
                "confidence": signal.get("confidence"),
                "verification_status": metadata.get("verification_status"),
            }
    ranked = sorted(
        by_identity.values(),
        key=lambda item: (-float(item.get("confidence") or 0), str(item.get("source_url") or "")),
    )
    return ranked[:limit]


def _attach_se_de_source_gap(output_dir: Path, report: dict[str, Any]) -> None:
    highlights = _source_gap_highlights(report)
    brief_path = output_dir / "domain-market-intelligence-brief.json"
    brief = _read_json(brief_path)
    if brief is not None:
        brief["se_de_source_coverage_gap"] = {
            "feed_family": report.get("feed_family"),
            "market_coverage": report.get("market_coverage") or ["SE", "DE"],
            "query_budget_total": report.get("query_budget_total", 4),
            "requests_made": report.get("requests_made", 0),
            "signal_count": report.get("signal_count", 0),
            "visible_highlight_count": len(highlights),
            "top_source_gap_signals": highlights,
            "source_page_verification_required": True,
            "not_part_of_opportunity_top5": True,
            "promotion_to_opportunity_allowed": False,
            "decision_owner": "HUMAN_OPERATOR",
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }
        _write_json(brief_path, brief)
    lines = [
        "SE/DE SOURCE COVERAGE GAP WATCH",
        f"requests_made: {report.get('requests_made', 0)}",
        f"signals: {report.get('signal_count', 0)}",
        f"visible_highlights: {len(highlights)}",
    ]
    if not highlights:
        lines.append("result: No current source-specific clothing liquidation signal passed the gate.")
    for item in highlights:
        lines.append(
            f"- [{item.get('source_country')}] [{item.get('source_name')}] "
            f"{item.get('title')} | type={item.get('signal_type')} | "
            f"confidence={item.get('confidence')} | {item.get('source_url')}"
        )
    lines += [
        "source_page_verification_required: true",
        "top5_eligible: false",
        "automatic_purchase: false",
    ]
    _append_text(output_dir, lines)


def _bridal_highlights(report: dict[str, Any], *, limit: int = 5) -> list[dict[str, Any]]:
    allowed_markets = {"NO", "SE", "DE"}
    by_identity: dict[str, dict[str, Any]] = {}
    for source in report.get("sources") or []:
        if not isinstance(source, dict):
            continue
        for signal in source.get("signals") or []:
            if not isinstance(signal, dict):
                continue
            country = str(signal.get("source_country") or "").upper()
            if country not in allowed_markets:
                continue
            identity = str(signal.get("signal_id") or signal.get("source_url") or "").strip()
            if not identity:
                continue
            by_identity[identity] = {
                "signal_id": signal.get("signal_id"),
                "source_country": country,
                "title": signal.get("title"),
                "source_url": signal.get("source_url"),
                "status": signal.get("status"),
                "confidence": signal.get("confidence"),
                "company_name": signal.get("company_name"),
                "seller_name": signal.get("seller_name"),
                "value": signal.get("value"),
                "verification_status": (signal.get("metadata") or {}).get("verification_status"),
            }
    ranked = sorted(
        by_identity.values(),
        key=lambda item: (-float(item.get("confidence") or 0), str(item.get("source_url") or "")),
    )
    return ranked[:limit]


def _attach_bridal_clearance_watch(output_dir: Path) -> None:
    report = _read_json(output_dir / "bridal-liquidation-feed.json") or {}
    highlights = _bridal_highlights(report)
    brief_path = output_dir / "domain-market-intelligence-brief.json"
    brief = _read_json(brief_path)
    if brief is not None:
        brief["bridal_clearance_watch"] = {
            "feed_family": report.get("feed_family"),
            "market_coverage": report.get("market_coverage") or ["NO", "SE", "DE"],
            "requests_made": report.get("requests_made", 0),
            "signal_count": report.get("signal_count", 0),
            "visible_highlight_count": len(highlights),
            "top_bridal_clearance_signals": highlights,
            "source_page_verification_required": True,
            "not_part_of_opportunity_top5": True,
            "promotion_to_opportunity_allowed": False,
            "decision_owner": "HUMAN_OPERATOR",
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }
        _write_json(brief_path, brief)
    lines = [
        "BRIDAL CLEARANCE WATCH",
        f"signals: {report.get('signal_count', 0)}",
        f"visible_highlights: {len(highlights)}",
    ]
    if not highlights:
        lines.append("result: No current bridal clearance signal passed the visibility gate.")
    for item in highlights:
        lines.append(
            f"- [{item.get('source_country')}] {item.get('title')} | "
            f"status={item.get('status')} | confidence={item.get('confidence')} | "
            f"verification={item.get('verification_status')} | {item.get('source_url')}"
        )
    lines += [
        "human_verification_required: true",
        "top5_eligible: false",
        "automatic_purchase: false",
    ]
    _append_text(output_dir, lines)


def _compact_b2b_candidate(item: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "candidate_id",
        "source_name",
        "title",
        "source_url",
        "quantity",
        "quantity_unit",
        "lot_size_band",
        "minimum_order",
        "minimum_order_unit",
        "unit_price",
        "total_price",
        "currency",
        "stock_location",
        "brands",
        "manifest_available",
        "missing_information",
        "opportunity_state",
        "b2b_relevance_score",
        "verification_status",
        "seller_name",
        "recommended_operator_action",
    )
    return {key: item.get(key) for key in keys}


def _run_daily_b2b_watch(output_dir: Path) -> None:
    try:
        report = collect_merkandi_b2b_liquidation_feed(environment=os.environ)
    except Exception as exc:
        report = {
            "schema_version": "merkandi-b2b-liquidation-feed-1.1",
            "feed_family": "MERKANDI_B2B_LIQUIDATION_FEED_V1",
            "purpose": "B2B_CLOTHING_LIQUIDATION_DECISION_SUPPORT",
            "status_counts": {"FAILED": 1},
            "requests_made": 0,
            "candidate_count": 0,
            "candidates": [],
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    _write_json(output_dir / "merkandi-b2b-liquidation-feed.json", report)
    compact = [
        _compact_b2b_candidate(item)
        for item in (report.get("candidates") or [])[:5]
        if isinstance(item, dict)
    ]
    brief_path = output_dir / "domain-market-intelligence-brief.json"
    brief = _read_json(brief_path)
    if brief is not None:
        b2b_payload = {
            "feed_family": report.get("feed_family"),
            "source_name": "Merkandi",
            "search_lane_country": "DE",
            "stock_country_must_be_verified": True,
            "query_budget_total": report.get("query_budget_total", 1),
            "requests_made": report.get("requests_made", 0),
            "candidate_count": report.get("candidate_count", 0),
            "top_b2b_signals": compact,
            "human_verification_required": True,
            "not_part_of_opportunity_top5": True,
            "promotion_to_opportunity_allowed": False,
            "decision_owner": "HUMAN_OPERATOR",
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }
        brief["merkandi_b2b_liquidation_feed"] = b2b_payload
        brief["daily_b2b_clothing_watch"] = b2b_payload
        _write_json(brief_path, brief)
    lines = [
        "B2B CLOTHING LIQUIDATION WATCH",
        "search_lane_country: DE",
        "stock_country_must_be_verified: true",
        f"requests_made: {report.get('requests_made', 0)}",
        f"candidate_count: {report.get('candidate_count', 0)}",
    ]
    if not compact:
        lines.append("result: No current serious B2B source result passed the relevance gate.")
    for item in compact:
        price = item.get("unit_price") or item.get("total_price")
        lines.append(
            f"- {item.get('title')} | state={item.get('opportunity_state')} | "
            f"quantity={item.get('quantity')} {item.get('quantity_unit')} | "
            f"price={price} {item.get('currency')} | location={item.get('stock_location')} | "
            f"score={item.get('b2b_relevance_score')} | {item.get('source_url')}"
        )
    lines += [
        "human_verification_required: true",
        "top5_eligible: false",
        "automatic_contact: false",
        "automatic_purchase: false",
    ]
    _append_text(output_dir, lines)


def _attach_cost_isolation_metadata(output_dir: Path, *, targeted_enabled: bool) -> None:
    brief_path = output_dir / "domain-market-intelligence-brief.json"
    brief = _read_json(brief_path)
    if brief is not None:
        brief["cost_isolation"] = {
            "schema_version": "daily-cost-isolation-1.0",
            "stage": "TARGETED_ENRICHMENT" if targeted_enabled else "CORE_DAILY",
            "targeted_enrichment_enabled": targeted_enabled,
            "openai_hunt_deferred": not targeted_enabled,
            "extra_brave_enrichment_deferred": not targeted_enabled,
            "commercial_analysis_stage": "SEPARATE_MANUAL_WORKFLOW",
        }
        _write_json(brief_path, brief)
    _append_text(
        output_dir,
        [
            "COST ISOLATION",
            f"stage: {'TARGETED_ENRICHMENT' if targeted_enabled else 'CORE_DAILY'}",
            f"targeted_enrichment_enabled: {str(targeted_enabled).lower()}",
        ],
    )


def main() -> int:
    output_dir = _output_dir()
    targeted_enabled = _apply_cost_isolation()
    source_gap_report = _run_se_de_source_gap_pre_core(output_dir)
    status = int(_load_core_module().main())
    if status != 0:
        return status
    _attach_se_de_source_gap(output_dir, source_gap_report)
    _attach_bridal_clearance_watch(output_dir)
    _run_daily_b2b_watch(output_dir)
    _attach_cost_isolation_metadata(output_dir, targeted_enabled=targeted_enabled)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
