from datetime import datetime, timezone

from scripts.build_learning_engine import build_learning


def _decision(opportunity_id: str, decision: str = "WATCH") -> dict:
    return {
        "opportunity_id": opportunity_id,
        "final_decision": decision,
        "recommendation": decision,
        "missing_evidence": ["transport_cost_nok"],
        "expected_profit_nok": None,
        "maximum_safe_bid_nok": None,
    }


def test_learning_is_observation_only_and_does_not_rewrite_decision():
    history, metrics = build_learning(
        {"decisions": [_decision("one", "WATCH")]},
        {"items": []},
        {"items": []},
        now=datetime(2026, 7, 22, tzinfo=timezone.utc),
    )
    assert history["mode"] == "OBSERVATION_ONLY"
    assert history["automatic_weight_updates"] is False
    assert history["records"][0]["original_decision"] == "WATCH"
    assert history["records"][0]["latest_decision"] == "WATCH"
    assert metrics["weight_change_recommendations"] == []


def test_original_decision_is_immutable_across_runs():
    first, _ = build_learning(
        {"decisions": [_decision("one", "WATCH")]}, {"items": []}, {"items": []},
        now=datetime(2026, 7, 22, tzinfo=timezone.utc),
    )
    second, _ = build_learning(
        {"decisions": [_decision("one", "REJECT")]}, {"items": []}, {"items": []}, first,
        now=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )
    assert second["record_count"] == 1
    assert second["records"][0]["original_decision"] == "WATCH"
    assert second["records"][0]["latest_decision"] == "REJECT"


def test_metrics_count_decisions_and_missing_evidence():
    _, metrics = build_learning(
        {"decisions": [_decision("one", "WATCH"), _decision("two", "REJECT")]},
        {"items": []}, {"items": []},
        now=datetime(2026, 7, 22, tzinfo=timezone.utc),
    )
    assert metrics["total_opportunities"] == 2
    assert metrics["decision_counts"] == {"REJECT": 1, "WATCH": 1}
    assert metrics["top_missing_evidence"][0] == {"evidence": "transport_cost_nok", "count": 2}
    assert metrics["learning_status"] == "INSUFFICIENT_VERIFIED_OUTCOMES"


def test_completed_follow_up_is_observed_not_claimed_as_verified_outcome():
    history, metrics = build_learning(
        {"decisions": [_decision("one")]},
        {"items": []},
        {"items": [{"opportunity_id": "one", "completed_at": "2026-07-22T10:00:00+00:00"}]},
        now=datetime(2026, 7, 22, tzinfo=timezone.utc),
    )
    row = history["records"][0]
    assert row["outcome_status"] == "FOLLOW_UP_COMPLETED"
    assert row["outcome_verified"] is False
    assert metrics["verified_outcome_count"] == 0
