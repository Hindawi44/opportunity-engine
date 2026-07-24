import json
from pathlib import Path

from scripts.run_v32_continuous_opportunity_monitoring import build_monitoring_report


def _batch():
    return json.loads(Path("data/live_validation/v3.1-auksjonen-live-batch.json").read_text(encoding="utf-8"))


def test_first_run_detects_all_and_second_run_detects_none():
    batch = _batch()
    first, state = build_monitoring_report(batch, {})
    assert first["opportunities_observed"] == 4
    assert first["new_opportunities_detected"] == 4
    assert first["automatic_purchase_decision"] is False
    assert first["errors"] == []
    assert first["status"] in {"NEW_OPPORTUNITIES_EVALUATED", "REVIEW_READY"}

    second, next_state = build_monitoring_report(batch, state)
    assert second["new_opportunities_detected"] == 0
    assert second["previously_seen_count"] == 4
    assert second["ready_for_financial_review"] == 0
    assert second["automatic_purchase_decision"] is False
    assert second["errors"] == []
    assert second["status"] == "NO_NEW_OPPORTUNITIES"
    assert next_state["seen_fingerprints"] == state["seen_fingerprints"]
