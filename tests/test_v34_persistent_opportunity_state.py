from scripts.run_v34_persistent_opportunity_state import build_lifecycle_report


def _item(listing_id: str, price: float, title: str = "Lot", status: str = "ACTIVE") -> dict:
    return {
        "listing_id": listing_id,
        "source_name": "auksjonen",
        "title": title,
        "description": "real listing",
        "url": f"https://www.auksjonen.no/auksjoner/{listing_id}",
        "auction_price_nok": price,
        "location": "Trøndelag",
        "listing_status": status,
    }


def test_v34_two_snapshot_lifecycle_and_v32_handoff():
    first = {
        "captured_at": "2026-07-24T10:00:00Z",
        "source_page": "https://www.auksjonen.no/auksjoner/overskuddsvarer/vareparti-og-konkursbo",
        "opportunities": [_item("100", 10000), _item("200", 20000), _item("300", 30000)],
    }
    first_report, first_state, first_monitoring = build_lifecycle_report(first, {}, {})
    assert first_report["lifecycle_counts"] == {
        "NEW": 3, "UPDATED": 0, "UNCHANGED": 0, "REMOVED": 0, "ARCHIVED": 0
    }
    assert first_report["actionable_count"] == 3
    assert first_report["passed_to_v3_2"] == 3

    second = {
        "captured_at": "2026-07-24T11:00:00Z",
        "source_page": first["source_page"],
        "opportunities": [
            _item("100", 10000),
            _item("200", 17500, title="Lot updated"),
            _item("400", 40000),
        ],
    }
    second_report, second_state, second_monitoring = build_lifecycle_report(
        second, first_state, first_monitoring
    )
    assert second_report["lifecycle_counts"] == {
        "NEW": 1, "UPDATED": 1, "UNCHANGED": 1, "REMOVED": 1, "ARCHIVED": 0
    }
    assert second_report["actionable_count"] == 2
    assert set(second_report["actionable_opportunity_ids"]) == {"auksjonen:200", "auksjonen:400"}
    assert second_report["automatic_purchase_decision"] is False
    assert second_report["errors"] == []
    assert second_report["status"] == "PASS"

    third_report, third_state, _ = build_lifecycle_report(second, second_state, second_monitoring)
    assert third_report["lifecycle_counts"] == {
        "NEW": 0, "UPDATED": 0, "UNCHANGED": 3, "REMOVED": 0, "ARCHIVED": 1
    }
    assert third_report["actionable_count"] == 0
    assert third_report["passed_to_v3_2"] == 0
    assert third_state["records"]["auksjonen:300"]["lifecycle_status"] == "ARCHIVED"
