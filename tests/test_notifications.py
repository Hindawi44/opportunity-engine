from __future__ import annotations

import json

from opportunity_engine.ods.autonomous_agent import AgentAlert
from opportunity_engine.ods.notifications import TelegramNotifier, format_alert


def _alert() -> AgentAlert:
    return AgentAlert(
        opportunity_id="lead-1",
        title="Example AS",
        change_type="NEW",
        decision="WATCH",
        decision_score=55.0,
        reason="Evidence is incomplete.",
    )


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_format_alert_contains_grounded_decision_fields() -> None:
    message = format_alert(_alert())
    assert "Example AS" in message
    assert "WATCH" in message
    assert "55.0/100" in message
    assert "Evidence is incomplete" in message


def test_notifier_skips_when_no_alerts() -> None:
    result = TelegramNotifier("token", "chat").send(())
    assert result.skipped is True
    assert result.attempted == 0


def test_notifier_skips_without_credentials() -> None:
    result = TelegramNotifier(None, None).send((_alert(),))
    assert result.skipped is True
    assert result.delivered == 0
    assert "not configured" in result.errors[0]


def test_notifier_delivers_successfully() -> None:
    requests = []

    def opener(req, timeout):
        requests.append((req, timeout))
        return FakeResponse({"ok": True, "result": {"message_id": 1}})

    result = TelegramNotifier("token", "chat", opener=opener).send((_alert(),))
    assert result.delivered == 1
    assert result.failed == 0
    assert len(requests) == 1
    assert requests[0][0].full_url.endswith("/bottoken/sendMessage")


def test_notifier_records_api_failure_without_raising() -> None:
    def opener(req, timeout):
        return FakeResponse({"ok": False, "description": "bad chat"})

    result = TelegramNotifier("token", "chat", opener=opener).send((_alert(),))
    assert result.delivered == 0
    assert result.failed == 1
    assert "bad chat" in result.errors[0]
