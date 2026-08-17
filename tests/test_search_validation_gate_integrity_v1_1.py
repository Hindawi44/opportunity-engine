from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.discovery.search_validation_gate_integrity import (
    build_integrity_search_validation_report,
    load_integrity_observations,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _auksjonen_run(root: Path, object_id: int) -> None:
    _write_json(
        root / "multi-market-inputs" / "no-auksjonen" / "auksjonen-live-clothing-listings.json",
        {
            "schema_version": "auksjonen-live-clothing-1.0",
            "captured_at": "2026-08-17T05:00:00Z",
            "reported_size": 60,
            "items_received": 60,
            "valid_inventory_opportunity_count": 1,
            "inventory_lot_count": 1,
            "top5_count": 1,
            "listings": [
                {
                    "object_id": object_id,
                    "title": f"Clothing lot {object_id}",
                    "url": f"https://ny.auksjonen.no/auksjon/torget/lot/{object_id}",
                    "listing_status": "ACTIVE",
                    "inventory_lot_signal": True,
                }
            ],
            "errors": [],
            "paid_search_used": False,
        },
    )


def test_legacy_query_diagnostics_without_status_are_counted_from_numeric_evidence(
    tmp_path: Path,
) -> None:
    path = tmp_path / "run1" / "multi-market-inputs" / "se-blinto" / "search-run-report.json"
    _write_json(
        path,
        {
            "execution_status": "PASS",
            "status": "PASS",
            "market_code": "SE",
            "source_target": "blinto.se",
            "queries_submitted": 2,
            "strong_leads_requiring_verification": 0,
            "merged_candidates": 2,
            "confirmed_sales": 0,
            "top5_count": 0,
            "analysis_eligible_count": 0,
            "source_diagnostics": {
                "requests_made": 2,
                "raw_hits": 3,
                "accepted_hits": 2,
                "rejected_hits": 1,
                "query_diagnostics": [
                    {"query_id": "q1", "raw_hits": 1, "accepted_hits": 1, "rejected_hits": 0},
                    {"query_id": "q2", "raw_hits": 2, "accepted_hits": 1, "rejected_hits": 1},
                ],
            },
        },
    )
    rows = load_integrity_observations([tmp_path / "run1"])
    assert len(rows) == 1
    assert rows[0].queries_attempted == 2
    assert rows[0].queries_succeeded == 2


def test_same_verified_listing_repeated_three_days_is_not_search_proof(tmp_path: Path) -> None:
    runs = []
    for index in range(1, 4):
        run = tmp_path / f"run{index}"
        _auksjonen_run(run, 619341)
        runs.append(run)

    report = build_integrity_search_validation_report(runs, required_markets=["NO"])
    source = next(row for row in report["sources"] if row["source_name"] == "Auksjonen Public API")

    assert source["run_count"] == 3
    assert source["verified_active_run_count"] == 3
    assert source["distinct_verified_active_identity_count"] == 1
    assert source["verdict"] == "NOT_PROVEN"
    assert "DISTINCT_VERIFIED_ACTIVE_LEADS_NOT_PROVEN" in source["reasons"]
    assert report["overall_verdict"] == "NOT_PROVEN"
    assert report["progression_gate_open"] is False


def test_two_distinct_verified_active_listings_can_satisfy_identity_proof(tmp_path: Path) -> None:
    run1 = tmp_path / "run1"
    run2 = tmp_path / "run2"
    run3 = tmp_path / "run3"
    _auksjonen_run(run1, 619341)
    _auksjonen_run(run2, 619341)
    _auksjonen_run(run3, 700002)

    report = build_integrity_search_validation_report(
        [run1, run2, run3], required_markets=["NO"]
    )
    source = next(row for row in report["sources"] if row["source_name"] == "Auksjonen Public API")

    assert source["distinct_verified_active_identity_count"] == 2
    assert source["verdict"] == "PROVEN"
    assert report["overall_verdict"] == "PROVEN"
    assert report["progression_gate_open"] is True


def test_integrity_gate_remains_offline(tmp_path: Path) -> None:
    run = tmp_path / "run1"
    _auksjonen_run(run, 619341)
    report = build_integrity_search_validation_report([run], required_markets=["NO"])
    assert report["integrity_correction"]["external_api_calls"] is False
    assert report["integrity_correction"]["brave_requests"] == 0
