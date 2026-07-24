import json
from pathlib import Path

from scripts.run_v211_live_opportunity_validation import build_report


def test_live_snapshot_preserves_missing_evidence_as_null_and_blocks_review():
    snapshot = json.loads(
        Path("data/live_validation/v2.11-auksjonen-berryalloc-route66.json").read_text(encoding="utf-8")
    )
    report = build_report(snapshot)

    assert report["live_snapshot_valid"] is True
    assert report["market_sources_observed"] == 3
    assert report["verified_comparable_count"] == 0
    assert report["verified_cost_component_count"] == 1
    assert report["market_status"] == "INCOMPLETE"
    assert report["cost_status"] == "INCOMPLETE"
    assert report["true_acquisition_cost_nok"] is None
    assert report["expected_profit_nok"] is None
    assert report["roi_percent"] is None
    assert report["decision_gate"] == "EVIDENCE_REQUIRED"
    assert report["automatic_purchase_decision"] is False
    assert report["evidence_trace_complete"] is True
    assert report["status"] == "IN_PROGRESS"
    assert "lot_quantity_m2" in report["missing_required_evidence"]
    assert report["errors"] == []
