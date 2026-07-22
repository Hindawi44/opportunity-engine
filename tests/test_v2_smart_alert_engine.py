from opportunity_engine.smart_alert_engine import build_smart_alerts


def opportunity(opportunity_id: str, decision: str, title: str = "Test"):
    return {
        "opportunity_id": opportunity_id,
        "final_decision": decision,
        "title": title,
        "city": "Namsos",
        "asking_price_nok": 1000,
        "opportunity_score": 80,
        "url": "https://example.test/item",
    }


def test_alerts_only_for_new_strong_opportunity():
    payload, state, sent = build_smart_alerts([
        opportunity("watch", "WATCH"),
        opportunity("strong", "BUY_REVIEW"),
        opportunity("reject", "REJECT"),
    ])
    assert payload["alert_count"] == 1
    assert payload["alerts"][0]["opportunity_id"] == "strong"
    assert state == {"watch": "WATCH", "strong": "BUY_REVIEW", "reject": "REJECT"}
    assert len(sent) == 1


def test_alerts_when_decision_changes():
    payload, _, _ = build_smart_alerts(
        [opportunity("x", "BUY_REVIEW")],
        previous_state={"x": "WATCH"},
    )
    assert payload["alert_count"] == 1
    assert payload["alerts"][0]["event_type"] == "DECISION_CHANGED"
    assert payload["alerts"][0]["old_decision"] == "WATCH"
    assert payload["alerts"][0]["new_decision"] == "BUY_REVIEW"


def test_duplicate_fingerprint_is_not_sent_again():
    first, state, sent = build_smart_alerts(
        [opportunity("x", "BUY_REVIEW")],
        previous_state={"x": "WATCH"},
    )
    assert first["alert_count"] == 1
    second, _, _ = build_smart_alerts(
        [opportunity("x", "BUY_REVIEW")],
        previous_state={"x": "WATCH"},
        sent_fingerprints=sent,
    )
    assert second["alert_count"] == 0


def test_message_is_mobile_short_and_contains_link_separately():
    payload, _, _ = build_smart_alerts([opportunity("x", "BUY_REVIEW", "فرصة قوية")])
    alert = payload["alerts"][0]
    assert len(alert["message_ar"]) < 400
    assert alert["url"] == "https://example.test/item"
    assert alert["automatic_purchase"] is False
    assert alert["automatic_bid"] is False


def test_evidence_required_is_treated_as_watch():
    payload, state, _ = build_smart_alerts([
        {"opportunity_id": "x", "final_decision": "EVIDENCE_REQUIRED"}
    ])
    assert payload["alert_count"] == 0
    assert state["x"] == "WATCH"
