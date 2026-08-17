import json

from opportunity_engine.discovery.search_validation_gate_integrity import (
    SearchValidationIntegrityPolicy,
)
from opportunity_engine.discovery.search_validation_gate_norway_official import (
    ENGINE_VERSION,
    build_norway_official_search_validation_report,
    collect_norway_official_identities,
    load_norway_official_observations,
)


def _policy() -> SearchValidationIntegrityPolicy:
    return SearchValidationIntegrityPolicy(
        min_live_runs=2,
        min_retrieval_success_rate=1.0,
        min_productive_run_rate=1.0,
        min_verified_active_runs=2,
        min_distinct_verified_active_leads=2,
    )


def _write_vareauksjonen(run_dir, listing_id: int, **overrides) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "listing_id": listing_id,
        "title": f"Clothing lot {listing_id}",
        "url": f"https://www.vareauksjonen.no/Listing/Details/{listing_id}/lot",
        "listing_status": "ACTIVE",
        "clothing_signal": True,
        "inventory_lot_signal": True,
        "top5_eligible": True,
    }
    record.update(overrides)
    payload = {
        "schema_version": "vareauksjonen-live-clothing-1.0",
        "captured_at": f"2026-08-{listing_id % 20 + 1:02d}T10:00:00+00:00",
        "candidate_count": 3,
        "detail_pages_requested": 1,
        "inventory_opportunity_count": 1 if (
            record["listing_status"] == "ACTIVE"
            and record["clothing_signal"] is True
            and record["inventory_lot_signal"] is True
        ) else 0,
        "commercial_top5_count": 1,
        "scan_complete": True,
        "listings": [record],
        "errors": [],
        "paid_search_used": False,
    }
    (run_dir / "vareauksjonen-live-clothing-listings.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def _write_auksjoner_no(run_dir, auction_id: int, **overrides) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "auction_id": auction_id,
        "title": f"Inventory auction {auction_id}",
        "url": f"https://www.auksjoner.no/nb-NO/auctions/{auction_id}",
        "listing_status": "ACTIVE",
        "clothing_signal": True,
        "inventory_lot_signal": True,
        "top5_eligible": True,
        "analysis_eligible": True,
    }
    record.update(overrides)
    payload = {
        "schema_version": "auksjoner-no-live-clothing-1.0",
        "captured_at": f"2026-08-{auction_id % 20 + 1:02d}T11:00:00+00:00",
        "items_received": 4,
        "inventory_opportunity_count": 1 if (
            record["listing_status"] == "ACTIVE"
            and record["clothing_signal"] is True
            and record["inventory_lot_signal"] is True
        ) else 0,
        "commercial_top5_count": 1,
        "scan_complete": True,
        "auctions": [record],
        "errors": [],
        "paid_search_used": False,
    }
    (run_dir / "auksjoner-no-live-clothing-auctions.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def _source(report, source_name: str):
    return next(row for row in report["sources"] if row["source_name"] == source_name)


def test_vareauksjonen_is_loaded_as_free_canonical_norway_evidence(tmp_path):
    run = tmp_path / "run-1"
    _write_vareauksjonen(run, 101)

    rows = load_norway_official_observations([run])

    assert len(rows) == 1
    row = rows[0]
    assert row.market_code == "NO"
    assert row.source_name == "Vareauksjonen Public Pages"
    assert row.execution_status == "SUCCESS"
    assert row.paid_search is False
    assert row.paid_requests_made == 0
    assert row.verified_active_leads == 1
    assert row.actionable_leads == 1


def test_two_distinct_vareauksjonen_active_lots_can_prove_source(tmp_path):
    run1 = tmp_path / "run-1"
    run2 = tmp_path / "run-2"
    _write_vareauksjonen(run1, 101)
    _write_vareauksjonen(run2, 202)

    report = build_norway_official_search_validation_report(
        [run1, run2], policy=_policy(), required_markets=("NO",)
    )
    source = _source(report, "Vareauksjonen Public Pages")

    assert report["engine_version"] == ENGINE_VERSION
    assert source["verdict"] == "PROVEN"
    assert source["distinct_verified_active_identity_count"] == 2
    assert report["overall_verdict"] == "PROVEN"
    assert report["progression_gate_open"] is True
    assert report["integrity_correction"]["brave_requests"] == 0


def test_repeated_vareauksjonen_identity_does_not_fake_proof(tmp_path):
    run1 = tmp_path / "run-1"
    run2 = tmp_path / "run-2"
    _write_vareauksjonen(run1, 101)
    _write_vareauksjonen(run2, 101)

    report = build_norway_official_search_validation_report(
        [run1, run2], policy=_policy(), required_markets=("NO",)
    )
    source = _source(report, "Vareauksjonen Public Pages")

    assert source["verdict"] == "NOT_PROVEN"
    assert source["distinct_verified_active_identity_count"] == 1
    assert "DISTINCT_VERIFIED_ACTIVE_LEADS_NOT_PROVEN" in source["reasons"]
    assert report["overall_verdict"] == "NOT_PROVEN"


def test_auksjoner_no_auction_id_is_counted_as_distinct_identity(tmp_path):
    run1 = tmp_path / "run-1"
    run2 = tmp_path / "run-2"
    _write_auksjoner_no(run1, 301)
    _write_auksjoner_no(run2, 302)

    report = build_norway_official_search_validation_report(
        [run1, run2], policy=_policy(), required_markets=("NO",)
    )
    source = _source(report, "Auksjoner.no Current Auctions")

    assert source["verdict"] == "PROVEN"
    assert source["distinct_verified_active_identity_count"] == 2
    assert source["distinct_verified_active_identities"] == [
        "auction_id:301",
        "auction_id:302",
    ]


def test_inactive_non_clothing_and_non_lot_records_never_enter_identity_proof(tmp_path):
    run1 = tmp_path / "run-inactive"
    run2 = tmp_path / "run-non-clothing"
    run3 = tmp_path / "run-non-lot"
    _write_auksjoner_no(run1, 401, listing_status="NOT_ACTIVE_OR_UNVERIFIED")
    _write_auksjoner_no(run2, 402, clothing_signal=False)
    _write_auksjoner_no(run3, 403, inventory_lot_signal=False)

    identities = collect_norway_official_identities([run1, run2, run3])
    run_map = identities[("NO", "Auksjoner.no Current Auctions")]

    assert run_map["run-inactive"] == set()
    assert run_map["run-non-clothing"] == set()
    assert run_map["run-non-lot"] == set()
