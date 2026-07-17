from __future__ import annotations

import json

from opportunity_engine.ods.autonomous_agent import AgentAlert
from opportunity_engine.ods.notifications import (
    EmailNotifier,
    TelegramNotifier,
    format_alert,
    format_email_digest,
)


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


class FakeSMTP:
    instances = []

    def __init__(self, host, port, *, timeout, context) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.context = context
        self.login_args = None
        self.message = None
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def login(self, username, password) -> None:
        self.login_args = (username, password)

    def send_message(self, message) -> None:
        self.message = message


def test_format_alert_contains_grounded_decision_fields() -> None:
    message = format_alert(_alert())
    assert "Example AS" in message
    assert "WATCH" in message
    assert "55.0/100" in message
    assert "Evidence is incomplete" in message


def test_email_digest_contains_alert_and_safety_note() -> None:
    message = format_email_digest((_alert(),))
    assert "Example AS" in message
    assert "Verify source evidence" in message


def test_email_notifier_skips_when_no_alerts() -> None:
    result = EmailNotifier(
        smtp_host="smtp.gmail.com",
        smtp_port=465,
        username="sender@example.com",
        password="secret",
        recipient="recipient@example.com",
        smtp_factory=FakeSMTP,
    ).send(())
    assert result.skipped is True
    assert result.attempted == 0


def test_email_notifier_skips_without_credentials() -> None:
    result = EmailNotifier(
        smtp_host="smtp.gmail.com",
        smtp_port=465,
        username=None,
        password=None,
        recipient=None,
    ).send((_alert(),))
    assert result.skipped is True
    assert result.delivered == 0
    assert "not configured" in result.errors[0]


def test_email_notifier_sends_one_digest() -> None:
    FakeSMTP.instances.clear()
    result = EmailNotifier(
        smtp_host="smtp.gmail.com",
        smtp_port=465,
        username="sender@example.com",
        password="app-password",
        recipient="recipient@example.com",
        smtp_factory=FakeSMTP,
    ).send((_alert(),))

    assert result.delivered == 1
    assert result.failed == 0
    smtp = FakeSMTP.instances[0]
    assert smtp.login_args == ("sender@example.com", "app-password")
    assert smtp.message["To"] == "recipient@example.com"
    assert "Example AS" in smtp.message.get_content()


def test_email_notifier_records_failure_without_raising() -> None:
    class FailingSMTP(FakeSMTP):
        def send_message(self, message) -> None:
            raise RuntimeError("smtp rejected message")

    result = EmailNotifier(
        smtp_host="smtp.gmail.com",
        smtp_port=465,
        username="sender@example.com",
        password="app-password",
        recipient="recipient@example.com",
        smtp_factory=FailingSMTP,
    ).send((_alert(),))

    assert result.delivered == 0
    assert result.failed == 1
    assert "smtp rejected message" in result.errors[0]


def test_telegram_notifier_skips_when_no_alerts() -> None:
    result = TelegramNotifier("token", "chat").send(())
    assert result.skipped is True
    assert result.attempted == 0


def test_telegram_notifier_delivers_successfully() -> None:
    requests = []

    def opener(req, timeout):
        requests.append((req, timeout))
        return FakeResponse({"ok": True, "result": {"message_id": 1}})

    result = TelegramNotifier("token", "chat", opener=opener).send((_alert(),))
    assert result.delivered == 1
    assert result.failed == 0
    assert len(requests) == 1
    assert requests[0][0].full_url.endswith("/bottoken/sendMessage")
