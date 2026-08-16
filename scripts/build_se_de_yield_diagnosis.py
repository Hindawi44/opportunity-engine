#!/usr/bin/env python3
"""Diagnose Sweden/Germany opportunity yield without changing discovery rules.

The report answers where the funnel dies: retrieval, source inventory, verification,
or downstream eligibility. It consumes already-written checkpoint artifacts only.
No network access, source widening, query changes, or promotion decisions occur here.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SWEDEN_SOURCES = (
    ("se-blinto", "Blinto"),
    ("se-klaravik", "Klaravik"),
    ("se-psauction", "PS Auction"),
)
GERMANY_SOURCES = (
    ("de-dpv", "Deutsche Pfandverwertung", "dpv-active-diagnostics.json"),
    ("de-riegermann", "Riegermann", "riegermann-active-diagnostics.json"),
    ("de-venta", "VENTA", "venta-active-diagnostics.json"),
)


def _read(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _count(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def _sweden_source(input_root: Path, directory: str, source_name: str) -> dict[str, Any]:
    report = _read(input_root / directory / "search-run-report.json")
    diagnostics = report.get("source_diagnostics")
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    requests = _count(diagnostics.get("requests_made") or report.get("queries_submitted"))
    raw_hits = _count(diagnostics.get("raw_hits"))
    accepted_hits = _count(diagnostics.get("accepted_hits"))
    rejected_hits = _count(diagnostics.get("rejected_hits"))
    merged_candidates = _count(report.get("merged_candidates"))
    verification_failures = _count(report.get("verification_failures"))
    analysis_eligible = _count(report.get("analysis_eligible_count"))
    return {
        "directory": directory,
        "source_name": source_name,
        "status": report.get("status"),
        "requests": requests,
        "raw_hits": raw_hits,
        "accepted_hits": accepted_hits,
        "rejected_hits": rejected_hits,
        "merged_candidates": merged_candidates,
        "verification_failures": verification_failures,
        "analysis_eligible_count": analysis_eligible,
        "raw_hits_per_request": _ratio(raw_hits, requests),
        "accepted_hits_per_request": _ratio(accepted_hits, requests),
        "rejection_reasons": diagnostics.get("rejection_reasons") or {},
    }


def _germany_source(input_root: Path, directory: str, source_name: str, diag_file: str) -> dict[str, Any]:
    report = _read(input_root / directory / "search-run-report.json")
    diag = _read(input_root / directory / diag_file)
    active_containers = _count(
        diag.get("active_catalog_entries_discovered")
        or diag.get("active_clothing_entries_discovered")
        or diag.get("selected_auction_count")
    )
    selected_containers = _count(diag.get("selected_catalog_count") or diag.get("selected_auction_count"))
    successful_containers = _count(diag.get("successful_catalog_count") or diag.get("successful_auction_count"))
    item_urls = _count(diag.get("catalog_item_url_count") or diag.get("parsed_child_lot_count"))
    clothing_child_lots = _count(diag.get("clothing_child_lot_count") or diag.get("active_clothing_entries_discovered"))
    promoted_bulk = _count(diag.get("promoted_bulk_lot_count"))
    verified_bulk = _count(diag.get("verified_bulk_lot_count"))
    merged_candidates = _count(report.get("merged_candidates"))
    verification_failures = _count(report.get("verification_failures"))
    analysis_eligible = _count(report.get("analysis_eligible_count"))
    return {
        "directory": directory,
        "source_name": source_name,
        "status": report.get("status"),
        "active_containers_discovered": active_containers,
        "selected_containers": selected_containers,
        "successful_containers": successful_containers,
        "item_urls_or_child_lots_seen": item_urls,
        "clothing_child_lot_count": clothing_child_lots,
        "promoted_bulk_lot_count": promoted_bulk,
        "verified_bulk_lot_count": verified_bulk,
        "merged_candidates": merged_candidates,
        "verification_failures": verification_failures,
        "analysis_eligible_count": analysis_eligible,
        "zero_clothing_results_are_valid": diag.get("zero_clothing_results_are_valid"),
        "lexical_non_clothing_lot_count": _count(diag.get("lexical_non_clothing_lot_count")),
        "zero_count_category_false_positive_count": _count(diag.get("zero_count_category_false_positive_count")),
    }


def _diagnose_sweden(rows: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {
        "source_count": len(rows),
        "requests": sum(_count(row.get("requests")) for row in rows),
        "raw_hits": sum(_count(row.get("raw_hits")) for row in rows),
        "accepted_hits": sum(_count(row.get("accepted_hits")) for row in rows),
        "rejected_hits": sum(_count(row.get("rejected_hits")) for row in rows),
        "merged_candidates": sum(_count(row.get("merged_candidates")) for row in rows),
        "verification_failures": sum(_count(row.get("verification_failures")) for row in rows),
        "analysis_eligible_count": sum(_count(row.get("analysis_eligible_count")) for row in rows),
    }
    totals["raw_hits_per_request"] = _ratio(totals["raw_hits"], totals["requests"])
    totals["accepted_hits_per_request"] = _ratio(totals["accepted_hits"], totals["requests"])

    if totals["requests"] > 0 and totals["raw_hits"] <= max(1, totals["requests"] // 4) and totals["merged_candidates"] == 0:
        bottleneck = "UPSTREAM_RETRIEVAL_OR_INDEXING"
        evidence = (
            "Direct-source searches executed, but very few indexed results reached the candidate layer; "
            "the funnel dies before verification or downstream eligibility."
        )
        priority = (
            "Test source-native/category enumeration or a bounded wider indexing window before increasing downstream gate tolerance."
        )
    elif totals["raw_hits"] > 0 and totals["accepted_hits"] == 0:
        bottleneck = "RETRIEVED_RESULTS_LACK_CLOTHING_SCOPE"
        evidence = "Search returned results, but none passed the source-specific clothing/bulk scope gate."
        priority = "Audit query/source targeting before changing verification or opportunity thresholds."
    elif totals["merged_candidates"] > 0 and totals["analysis_eligible_count"] == 0:
        bottleneck = "VERIFICATION_OR_ELIGIBILITY"
        evidence = "Candidates exist, but none reached analysis-ready state."
        priority = "Inspect verification blockers and hard-gate reasons for candidate loss."
    else:
        bottleneck = "NO_SINGLE_DOMINANT_BOTTLENECK"
        evidence = "The observed counters do not isolate one dominant loss stage."
        priority = "Keep the current rules frozen and inspect per-source diagnostics."
    return {"totals": totals, "bottleneck": bottleneck, "evidence": evidence, "priority_action": priority}


def _diagnose_germany(rows: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {
        "source_count": len(rows),
        "active_containers_discovered": sum(_count(row.get("active_containers_discovered")) for row in rows),
        "selected_containers": sum(_count(row.get("selected_containers")) for row in rows),
        "successful_containers": sum(_count(row.get("successful_containers")) for row in rows),
        "item_urls_or_child_lots_seen": sum(_count(row.get("item_urls_or_child_lots_seen")) for row in rows),
        "clothing_child_lot_count": sum(_count(row.get("clothing_child_lot_count")) for row in rows),
        "promoted_bulk_lot_count": sum(_count(row.get("promoted_bulk_lot_count")) for row in rows),
        "verified_bulk_lot_count": sum(_count(row.get("verified_bulk_lot_count")) for row in rows),
        "merged_candidates": sum(_count(row.get("merged_candidates")) for row in rows),
        "verification_failures": sum(_count(row.get("verification_failures")) for row in rows),
        "analysis_eligible_count": sum(_count(row.get("analysis_eligible_count")) for row in rows),
    }
    if totals["successful_containers"] > 0 and totals["clothing_child_lot_count"] == 0 and totals["merged_candidates"] == 0:
        bottleneck = "CURRENT_SOURCE_INVENTORY_COVERAGE"
        evidence = (
            "German source-native watches successfully opened active catalogs/auctions, but the observed child lots contained no "
            "qualifying clothing inventory; the funnel dies before verification."
        )
        priority = (
            "Expand or rotate German direct-source coverage and early-signal follow-up; do not weaken verification gates for empty source inventory."
        )
    elif totals["merged_candidates"] > 0 and totals["analysis_eligible_count"] == 0:
        bottleneck = "VERIFICATION_OR_ELIGIBILITY"
        evidence = "German candidates exist, but none reached analysis-ready state."
        priority = "Inspect verification blockers and hard-gate reasons."
    elif totals["successful_containers"] == 0:
        bottleneck = "SOURCE_ACCESS_OR_ACTIVE_CATALOG_AVAILABILITY"
        evidence = "No German source-native catalog/auction was successfully inspected."
        priority = "Repair source access or active-catalog discovery before changing opportunity rules."
    else:
        bottleneck = "NO_SINGLE_DOMINANT_BOTTLENECK"
        evidence = "The observed counters do not isolate one dominant loss stage."
        priority = "Keep the current rules frozen and inspect per-source diagnostics."
    return {"totals": totals, "bottleneck": bottleneck, "evidence": evidence, "priority_action": priority}


def build_payload(input_root: Path) -> dict[str, Any]:
    sweden_rows = [_sweden_source(input_root, directory, name) for directory, name in SWEDEN_SOURCES]
    germany_rows = [_germany_source(input_root, directory, name, diag) for directory, name, diag in GERMANY_SOURCES]
    sweden = _diagnose_sweden(sweden_rows)
    germany = _diagnose_germany(germany_rows)
    sweden["sources"] = sweden_rows
    germany["sources"] = germany_rows
    return {
        "schema_version": "se-de-yield-diagnosis-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "READ_ONLY_DIAGNOSTIC",
        "rules_changed": False,
        "queries_changed": False,
        "sources_added": False,
        "promotion_logic_changed": False,
        "markets": {"SE": sweden, "DE": germany},
        "decision": (
            "Do not tune downstream gates from a zero-opportunity day. Sweden is primarily a retrieval/indexing problem; "
            "Germany is primarily a current direct-source inventory/coverage problem."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", default="artifacts/multi-market-inputs")
    parser.add_argument(
        "--output",
        default="artifacts/multi-market-daily-operator-checkpoint/se-de-yield-diagnosis.json",
    )
    args = parser.parse_args()
    payload = build_payload(Path(args.input_root))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "SE": payload["markets"]["SE"]["bottleneck"],
        "DE": payload["markets"]["DE"]["bottleneck"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
