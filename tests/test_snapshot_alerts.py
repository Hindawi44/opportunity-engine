import json

from opportunity_engine.ods.snapshot_alerts import SnapshotAlertProcessor


def _snapshot():
    return {
        "schema_version": 11,
        "generated_at": "2026-07-20T21:00:00+00:00",
        "rows": [
            {
                "opportunity_id": "unified-1",
                "title": "Butikkinnredning",
                "url": "https://example.com/1",
                "asking_price_nok": 10_000,
                "price_change_count": 1,
                "significant_price_drop": True,
                "decision": "buy",
                "expected_profit_nok": 8_000,
                "ends_at": "2026-07-21T18:00:00+00:00",
            }
        ],
        "discovery_by_id": {
            "unified-1": {
                "discovery_score": 84,
                "is_exceptional": True,
                "requires_immediate_review": True,
                "suggested_action": "راجع الفرصة الآن.",
            }
        },
        "intelligence_by_id": {
            "unified-1": {"summary": "خصم وربحية قويان مع بيانات مكتملة."}
        },
    }


def test_processor_creates_alert_and_updates_snapshot(tmp_path) -> None:
    snapshot = tmp_path / "today.json"
    alerts = tmp_path / "alerts.json"
    snapshot.write_text(json.dumps(_snapshot()), encoding="utf-8")

    created = SnapshotAlertProcessor().process(str(snapshot), str(alerts))

    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    state = json.loads(alerts.read_text(encoding="utf-8"))
    assert len(created) == 1
    assert created[0]["alert_type"] == "exceptional_opportunity"
    assert created[0]["severity"] == "critical"
    assert payload["schema_version"] == 12
    assert payload["alert_count"] == 1
    assert payload["alerts"][0]["opportunity_id"] == "unified-1"
    assert len(state["alerts"]) == 1


def test_processor_does_not_repeat_same_alert(tmp_path) -> None:
    snapshot = tmp_path / "today.json"
    alerts = tmp_path / "alerts.json"
    snapshot.write_text(json.dumps(_snapshot()), encoding="utf-8")
    processor = SnapshotAlertProcessor()

    assert len(processor.process(str(snapshot), str(alerts))) == 1
    snapshot.write_text(json.dumps(_snapshot()), encoding="utf-8")
    assert processor.process(str(snapshot), str(alerts)) == ()


def test_processor_emits_new_alert_after_price_change(tmp_path) -> None:
    snapshot = tmp_path / "today.json"
    alerts = tmp_path / "alerts.json"
    first = _snapshot()
    snapshot.write_text(json.dumps(first), encoding="utf-8")
    processor = SnapshotAlertProcessor()
    processor.process(str(snapshot), str(alerts))

    second = _snapshot()
    second["rows"][0]["asking_price_nok"] = 8_000
    second["rows"][0]["price_change_count"] = 2
    snapshot.write_text(json.dumps(second), encoding="utf-8")
    created = processor.process(str(snapshot), str(alerts))

    assert len(created) == 1
    assert created[0]["opportunity_id"] == "unified-1"


def test_processor_ignores_low_priority_opportunity(tmp_path) -> None:
    snapshot = tmp_path / "today.json"
    alerts = tmp_path / "alerts.json"
    payload = _snapshot()
    payload["rows"][0]["significant_price_drop"] = False
    payload["rows"][0]["decision"] = "monitor"
    payload["rows"][0]["expected_profit_nok"] = None
    payload["discovery_by_id"]["unified-1"].update(
        discovery_score=45,
        is_exceptional=False,
        requires_immediate_review=False,
    )
    snapshot.write_text(json.dumps(payload), encoding="utf-8")

    assert SnapshotAlertProcessor().process(str(snapshot), str(alerts)) == ()
