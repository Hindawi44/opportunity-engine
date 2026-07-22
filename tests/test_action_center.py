from datetime import datetime, timezone

from scripts.build_action_center import build_action_center


NOW = datetime(2026, 7, 22, 20, 0, tzinfo=timezone.utc)


def _decision(opportunity_id: str, final_decision: str, missing=None):
    return {
        "opportunity_id": opportunity_id,
        "title": opportunity_id,
        "url": f"https://example.test/{opportunity_id}",
        "final_decision": final_decision,
        "recommendation": final_decision,
        "missing_evidence": missing or [],
        "missing_evidence_ar": ["ثلاث مقارنات سوقية موثقة"] if missing else [],
        "requires_human_approval": final_decision == "BUY_REVIEW",
    }


def test_every_active_opportunity_has_next_action_and_watch_has_due_date():
    payload = {
        "decisions": [
            _decision("watch-1", "WATCH", ["three_verified_market_comparables"]),
            _decision("buy-1", "BUY_REVIEW"),
        ]
    }
    actions, followups, closed, history = build_action_center(payload, now=NOW)

    assert actions["action_count"] == 2
    assert all(item["next_action"] for item in actions["items"])
    watch = next(item for item in actions["items"] if item["final_decision"] == "WATCH")
    assert watch["due_at"] is not None
    assert watch["next_action"] == "VERIFY_MARKET_PRICE"
    assert followups["follow_up_count"] == 1
    assert closed["closed_count"] == 0
    assert history["event_count"] == 2


def test_reject_is_closed_and_never_enters_action_queue():
    payload = {"decisions": [_decision("reject-1", "REJECT")]}
    actions, followups, closed, _ = build_action_center(payload, now=NOW)

    assert actions["items"] == []
    assert followups["items"] == []
    assert closed["closed_count"] == 1
    assert closed["items"][0]["next_action"] == "CLOSE_OPPORTUNITY"


def test_decision_history_only_adds_events_when_decision_or_action_changes():
    payload = {"decisions": [_decision("watch-1", "WATCH", ["transport_cost_nok"])]}
    first = build_action_center(payload, now=NOW)
    second = build_action_center(payload, previous_history=first[3], now=NOW)

    assert first[3]["event_count"] == 1
    assert second[3]["event_count"] == 1


def test_inconsistent_legacy_recommendation_is_rejected():
    payload = {"decisions": [{
        **_decision("bad-1", "WATCH"),
        "recommendation": "REJECT",
    }]}

    try:
        build_action_center(payload, now=NOW)
    except ValueError as exc:
        assert "decision inconsistency" in str(exc)
    else:
        raise AssertionError("expected decision consistency invariant to fail")
