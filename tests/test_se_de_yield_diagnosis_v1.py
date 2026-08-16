from __future__ import annotations

import json
from pathlib import Path

from scripts.build_se_de_yield_diagnosis import build_payload


def _write(root: Path, relative: str, payload: dict) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_run186_shape_identifies_upstream_sweden_and_inventory_coverage_germany(tmp_path: Path) -> None:
    for directory, raw, rejected in (("se-blinto", 0, 0), ("se-klaravik", 3, 3), ("se-psauction", 1, 1)):
        _write(
            tmp_path,
            f"{directory}/search-run-report.json",
            {
                "status": "PASS",
                "queries_submitted": 8,
                "merged_candidates": 0,
                "verification_failures": 0,
                "analysis_eligible_count": 0,
                "source_diagnostics": {
                    "requests_made": 8,
                    "raw_hits": raw,
                    "accepted_hits": 0,
                    "rejected_hits": rejected,
                },
            },
        )

    _write(tmp_path, "de-dpv/search-run-report.json", {"status": "PASS", "merged_candidates": 0})
    _write(tmp_path, "de-dpv/dpv-active-diagnostics.json", {
        "active_catalog_entries_discovered": 2,
        "selected_catalog_count": 2,
        "successful_catalog_count": 2,
        "catalog_item_url_count": 2,
        "clothing_child_lot_count": 0,
        "promoted_bulk_lot_count": 0,
        "zero_clothing_results_are_valid": True,
    })
    _write(tmp_path, "de-riegermann/search-run-report.json", {"status": "PASS", "merged_candidates": 0})
    _write(tmp_path, "de-riegermann/riegermann-active-diagnostics.json", {
        "active_clothing_entries_discovered": 0,
        "selected_auction_count": 0,
        "successful_auction_count": 0,
        "parsed_child_lot_count": 0,
        "promoted_bulk_lot_count": 0,
    })
    _write(tmp_path, "de-venta/search-run-report.json", {"status": "PASS", "merged_candidates": 0})
    _write(tmp_path, "de-venta/venta-active-diagnostics.json", {
        "active_catalog_entries_discovered": 5,
        "selected_catalog_count": 5,
        "successful_catalog_count": 5,
        "catalog_item_url_count": 587,
        "clothing_child_lot_count": 0,
        "promoted_bulk_lot_count": 0,
        "zero_clothing_results_are_valid": True,
    })

    result = build_payload(tmp_path)

    assert result["markets"]["SE"]["bottleneck"] == "UPSTREAM_RETRIEVAL_OR_INDEXING"
    assert result["markets"]["SE"]["totals"]["requests"] == 24
    assert result["markets"]["SE"]["totals"]["raw_hits"] == 4
    assert result["markets"]["SE"]["totals"]["merged_candidates"] == 0

    assert result["markets"]["DE"]["bottleneck"] == "CURRENT_SOURCE_INVENTORY_COVERAGE"
    assert result["markets"]["DE"]["totals"]["successful_containers"] == 7
    assert result["markets"]["DE"]["totals"]["item_urls_or_child_lots_seen"] == 589
    assert result["markets"]["DE"]["totals"]["clothing_child_lot_count"] == 0
    assert result["rules_changed"] is False
    assert result["queries_changed"] is False
    assert result["sources_added"] is False


def test_candidates_without_analysis_ready_are_not_misdiagnosed_as_retrieval(tmp_path: Path) -> None:
    for directory in ("se-blinto", "se-klaravik", "se-psauction"):
        _write(
            tmp_path,
            f"{directory}/search-run-report.json",
            {
                "status": "PASS",
                "queries_submitted": 4,
                "merged_candidates": 2,
                "verification_failures": 1,
                "analysis_eligible_count": 0,
                "source_diagnostics": {
                    "requests_made": 4,
                    "raw_hits": 8,
                    "accepted_hits": 2,
                    "rejected_hits": 6,
                },
            },
        )
    result = build_payload(tmp_path)
    assert result["markets"]["SE"]["bottleneck"] == "VERIFICATION_OR_ELIGIBILITY"
