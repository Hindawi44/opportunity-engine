from __future__ import annotations

from pathlib import Path
import sqlite3

from opportunity_engine.discovery.auksjonen_public_api_adapter import (
    AuksjonenLiveClothingCollection,
    AuksjonenLiveClothingListing,
)
from opportunity_engine.discovery.auksjonen_unified_lifecycle import (
    AUKSJONEN_ANALYSIS_BLOCKERS,
    build_auksjonen_discovery_result,
    build_auksjonen_unified_report,
    write_auksjonen_unified_artifacts,
)
from opportunity_engine.discovery.checkpoint_state_restore import (
    DATABASE_RELATIVE_PATHS,
)
from opportunity_engine.persistence.live_unified_persistence import (
    persist_unified_report_with_artifacts,
)


def _listing(object_id: int, title: str) -> AuksjonenLiveClothingListing:
    return AuksjonenLiveClothingListing(
        title=title,
        url=f"https://ny.auksjonen.no/auksjon/torget/test/{object_id}",
        auction_id=9000 + object_id,
        object_id=object_id,
        status="ACTIVE",
        listing_status="ACTIVE",
        current_bid_nok=1000.0,
        buy_now_price_nok=None,
        start_price_nok=500.0,
        bid_count=2,
        bidder_count=1,
        city="Namsos",
        zip_code="7800",
        address=None,
        ends_at="2026-08-05T12:00:00+00:00",
        main_image=None,
        inventory_lot_signal=True,
    )


def _collection() -> AuksjonenLiveClothingCollection:
    listings = (
        _listing(101, "10 stk arbeidsjakker"),
        _listing(102, "Parti med arbeidsbukser"),
    )
    return AuksjonenLiveClothingCollection(
        captured_at="2026-08-03T06:40:00+00:00",
        endpoint="https://ny.auksjonen.no/api/category-search/search?category2=10110508&from=1&to=30&asc=true&orderBy=endTime",
        reported_size=2,
        items_received=2,
        listings=listings,
        pages_fetched=1,
        page_size=30,
        errors=(),
    )


def test_auksjonen_inventory_lots_use_unified_verification_lifecycle() -> None:
    collection = _collection()
    discovery = build_auksjonen_discovery_result(collection)
    candidates = discovery["all_discovered_candidates"]

    assert len(candidates) == 2
    assert candidates[0]["opportunity_identity"] == collection.listings[0].url
    assert candidates[0]["identity_stable"] is True
    assert candidates[0]["top5_eligible"] is True
    assert candidates[0]["analysis_eligible"] is False
    assert candidates[0]["missing_information"] == list(AUKSJONEN_ANALYSIS_BLOCKERS)
    assert candidates[0]["location"] == "7800, Namsos"

    _, report = build_auksjonen_unified_report(collection)
    assert report["schema_version"] == "1.1"
    assert report["record_count"] == 2
    assert report["conversion_error_count"] == 0
    first = report["records"][0]
    assert first["workflow_status"] == "REQUIRES_VERIFICATION"
    assert first["evaluation_status"] == "REQUIRES_VERIFICATION"
    assert first["listing_status"] == "ACTIVE"
    assert first["verified"] is False
    assert first["analysis_eligible"] is False
    assert first["top5_eligible"] is True
    assert first["metadata"]["lifecycle_reason_code"] == "MISSING_REQUIRED_VERIFICATION"
    assert [item["field_name"] for item in first["missing_information"]] == list(
        AUKSJONEN_ANALYSIS_BLOCKERS
    )


def test_auksjonen_sqlite_lifecycle_replay_is_idempotent(tmp_path: Path) -> None:
    paths = write_auksjonen_unified_artifacts(_collection(), tmp_path)
    database_path = tmp_path / "opportunity_engine.db"
    database_url = f"sqlite:///{database_path}"

    first, first_summary_path = persist_unified_report_with_artifacts(
        paths["unified_opportunity_report"],
        tmp_path,
        database_url=database_url,
    )
    assert first_summary_path.exists()
    assert first["persisted_record_count"] == 2
    assert first["lifecycle_events_created"] == 2

    second, _ = persist_unified_report_with_artifacts(
        paths["unified_opportunity_report"],
        tmp_path,
        database_url=database_url,
    )
    assert second["persisted_record_count"] == 2
    assert second["lifecycle_events_created"] == 0

    connection = sqlite3.connect(database_path)
    try:
        opportunity_count = connection.execute(
            "SELECT COUNT(*) FROM unified_opportunities"
        ).fetchone()[0]
        lifecycle_count = connection.execute(
            "SELECT COUNT(*) FROM lifecycle_events"
        ).fetchone()[0]
    finally:
        connection.close()
    assert opportunity_count == 2
    assert lifecycle_count == 2


def test_previous_checkpoint_restore_includes_auksjonen_database() -> None:
    assert "no-auksjonen/opportunity_engine.db" in DATABASE_RELATIVE_PATHS
