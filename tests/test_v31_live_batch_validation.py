import json
from pathlib import Path

from scripts.run_v31_live_batch_validation import build_batch_report


def test_real_batch_is_evaluated_without_inventing_missing_evidence():
    batch = json.loads(Path("data/live_validation/v3.1-auksjonen-live-batch.json").read_text(encoding="utf-8"))
    report = build_batch_report(batch)

    assert report["opportunities_received"] == 4
    assert report["opportunities_evaluated"] == 4
    assert report["active_opportunities"] == 2
    assert report["ready_for_financial_review"] == 0
    assert report["excluded_count"] == 4
    assert report["rankings"] == []
    assert report["automatic_purchase_decision"] is False
    assert report["errors"] == []
    assert report["status"] == "IN_PROGRESS"
    assert all(item["decision_gate"] == "EVIDENCE_REQUIRED" for item in report["evaluations"])
    assert all(item["expected_profit_nok"] is None for item in report["evaluations"])
