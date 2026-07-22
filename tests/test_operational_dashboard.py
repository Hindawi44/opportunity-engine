import json
from pathlib import Path

from opportunity_engine.operational_dashboard import build_snapshot, canonical_decision


def write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_canonical_decision_prefers_final_decision():
    assert canonical_decision({"final_decision": "WATCH", "recommendation": "REJECT"}) == "WATCH"
    assert canonical_decision({"decision": "EVIDENCE_REQUIRED"}) == "WATCH"


def test_snapshot_counts_and_overdue_followups(tmp_path: Path):
    write(tmp_path / "decision_intelligence.json", {
        "buy_review_count": 1,
        "watch_count": 1,
        "reject_count": 1,
        "decisions": [
            {"opportunity_id": "1", "final_decision": "BUY_REVIEW"},
            {"opportunity_id": "2", "final_decision": "WATCH"},
            {"opportunity_id": "3", "final_decision": "REJECT"},
        ],
    })
    write(tmp_path / "action_queue.json", {"queue": []})
    write(tmp_path / "follow_up_status.json", {
        "records": [
            {"opportunity_id": "2", "status": "OVERDUE"},
            {"opportunity_id": "4", "status": "PENDING"},
        ]
    })
    write(tmp_path / "discovery_health.json", {"status": "HEALTHY"})
    write(tmp_path / "learning_metrics.json", {
        "mode": "OBSERVATION_ONLY",
        "automatic_weight_updates": False,
    })

    snapshot = build_snapshot(tmp_path)

    assert snapshot.counts == {"BUY_REVIEW": 1, "WATCH": 1, "REJECT": 1}
    assert len(snapshot.overdue_follow_ups) == 1
    assert snapshot.warnings == []
    assert snapshot.learning["automatic_weight_updates"] is False


def test_snapshot_reports_declared_count_conflict(tmp_path: Path):
    write(tmp_path / "decision_intelligence.json", {
        "watch_count": 9,
        "decisions": [{"final_decision": "WATCH"}],
    })
    for name in ("action_queue.json", "follow_up_status.json", "discovery_health.json", "learning_metrics.json"):
        write(tmp_path / name, {})

    snapshot = build_snapshot(tmp_path)

    assert snapshot.counts["WATCH"] == 1
    assert any("تعارض عداد WATCH" in warning for warning in snapshot.warnings)
