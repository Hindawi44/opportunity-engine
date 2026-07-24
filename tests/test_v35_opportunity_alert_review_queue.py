from opportunity_engine.opportunity_review_queue import set_queue_status, update_review_queue


def candidate(opportunity_id: str, *, roi: float = 40.0, profit: float = 12000.0, version: str = "v1"):
    return {
        "opportunity_id": opportunity_id,
        "decision_gate": "READY_FOR_FINANCIAL_REVIEW",
        "automatic_purchase_decision": False,
        "verified_comparable_count": 3,
        "verified_cost_component_count": 6,
        "expected_profit": profit,
        "roi": roi,
        "evidence_version": version,
    }


def test_v35_alert_and_review_queue_e2e():
    ineligible = dict(candidate("missing-evidence"))
    ineligible["decision_gate"] = "EVIDENCE_REQUIRED"

    first, state1 = update_review_queue(
        [candidate("alpha", roi=60), candidate("beta", roi=30), ineligible],
        {},
        run_at="2026-07-24T12:00:00Z",
    )
    assert first["review_queue_created"] is True
    assert first["review_queue_count"] == 2
    assert first["new_alerts_count"] == 2
    assert first["duplicate_alerts"] == 0
    assert first["automatic_purchase_decision"] is False
    assert first["status"] == "PASS"
    assert [item["opportunity_id"] for item in first["queue"]] == ["alpha", "beta"]

    second, state2 = update_review_queue(
        [candidate("alpha", roi=60), candidate("beta", roi=30)],
        state1,
        run_at="2026-07-24T13:00:00Z",
    )
    assert second["new_alerts_count"] == 0
    assert second["duplicate_alerts"] == 0
    assert state2["alert_fingerprints"] == state1["alert_fingerprints"]

    state2 = set_queue_status(state2, "alpha", "SNOOZED", changed_at="2026-07-24T13:10:00Z")
    third, state3 = update_review_queue(
        [candidate("alpha", roi=75, profit=16000, version="v2"), candidate("beta", roi=30)],
        state2,
        run_at="2026-07-24T14:00:00Z",
    )
    assert third["new_alerts_count"] == 1
    assert third["alerts"][0]["opportunity_id"] == "alpha"
    assert third["alerts"][0]["reason"] == "MATERIAL_UPDATE"
    assert state3["items"]["alpha"]["queue_status"] == "SNOOZED"
    assert third["automatic_purchase_decision"] is False
