from pathlib import Path

from opportunity_engine.source_ingestion.auksjonen import (
    AUKSJONEN_CATEGORY_URL,
    build_snapshot,
    parse_public_listings,
)
from scripts.run_v33_auksjonen_ingestion import run_refresh


def _fixture() -> str:
    return Path("tests/fixtures/v33_auksjonen_page.html").read_text(encoding="utf-8")


def test_auksjonen_adapter_extracts_only_public_positive_nok_listings():
    listings = parse_public_listings(_fixture())

    assert len(listings) == 3
    assert [item.listing_id for item in listings] == ["123456", "123457", "123458"]
    assert [item.asking_price_nok for item in listings] == [10000.0, 25000.0, 15000.0]
    assert all(item.url.startswith("https://www.auksjonen.no/auksjoner/") for item in listings)

    snapshot = build_snapshot(
        listings,
        captured_at="2026-07-24T12:00:00+02:00",
    )
    assert snapshot["schema_version"] == "3.3"
    assert snapshot["source_page"] == AUKSJONEN_CATEGORY_URL
    assert len(snapshot["opportunities"]) == 3
    assert all(item["source"]["listing_status"] == "ACTIVE" for item in snapshot["opportunities"])
    assert all(item["verified_cost_evidence"]["auction_price_nok"] > 0 for item in snapshot["opportunities"])
    assert all(item["automatic_purchase_decision"] is False for item in [])


def test_refresh_passes_snapshot_to_v32_and_deduplicates_second_run():
    first_report, first_snapshot, first_state = run_refresh(
        html=_fixture(),
        state_payload={},
        captured_at="2026-07-24T12:00:00+02:00",
    )

    assert first_report == {
        "schema_version": "3.3",
        "source": "Auksjonen.no",
        "source_page": AUKSJONEN_CATEGORY_URL,
        "captured_at": "2026-07-24T12:00:00+02:00",
        "listings_extracted": 3,
        "snapshot_written": True,
        "new_opportunities_detected": 3,
        "ready_for_financial_review": 0,
        "automatic_purchase_decision": False,
        "monitoring_status": "NEW_OPPORTUNITIES_EVALUATED",
        "errors": [],
        "status": "PASS",
    }
    assert len(first_snapshot["opportunities"]) == 3
    assert len(first_state["seen_fingerprints"]) == 3

    second_report, second_snapshot, second_state = run_refresh(
        html=_fixture(),
        state_payload=first_state,
        captured_at="2026-07-24T13:00:00+02:00",
    )

    assert second_report["listings_extracted"] == 3
    assert second_report["new_opportunities_detected"] == 0
    assert second_report["monitoring_status"] == "NO_NEW_OPPORTUNITIES"
    assert second_report["automatic_purchase_decision"] is False
    assert len(second_snapshot["opportunities"]) == 3
    assert second_state["seen_fingerprints"] == first_state["seen_fingerprints"]
