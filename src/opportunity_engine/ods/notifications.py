"""Optional notification delivery for meaningful ODS agent alerts."""
from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
import json
import smtplib
import ssl
from typing import Callable, Iterable
from urllib import parse, request

from .autonomous_agent import AgentAlert


@dataclass(frozen=True)
class DeliveryResult:
    channel: str
    attempted: int
    delivered: int
    failed: int
    skipped: bool
    errors: tuple[str, ...] = ()


def format_alert(alert: AgentAlert) -> str:
    """Create a concise, evidence-grounded alert message."""
    return (
        "ODS opportunity update\n"
        f"Opportunity: {alert.title}\n"
        f"Change: {alert.change_type}\n"
        f"Decision: {alert.decision}\n"
        f"Decision score: {alert.decision_score:.1f}/100\n"
        f"Reason: {alert.reason}\n"
        f"ODS ID: {alert.opportunity_id}"
    )


def format_email_digest(alerts: Iterable[AgentAlert]) -> str:
    """Format one readable email containing all meaningful alerts from a run."""
    items = tuple(alerts)
    sections = [format_alert(alert) for alert in items]
    return (
        "ODS found new or materially changed opportunities.\n\n"
        + "\n\n------------------------------\n\n".join(sections)
        + "\n\nThis message is informational. Verify source evidence before acting."
    )


class EmailNotifier:
    """Send one digest email through a standard SMTP server.

    Missing credentials produce a skipped result. SMTP failures are recorded and do
    not crash the research cycle. Gmail users should provide an App Password rather
    than their normal account password.
    """

    def __init__(
        self,
        *,
        smtp_host: str | None,
        smtp_port: int | str | None,
        username: str | None,
        password: str | None,
        recipient: str | None,
        sender: str | None = None,
        timeout: float = 20.0,
        smtp_factory: Callable[..., object] = smtplib.SMTP_SSL,
    ) -> None:
        self.smtp_host = (smtp_host or "").strip()
        self.smtp_port = int(smtp_port or 465)
        self.username = (username or "").strip()
        self.password = password or ""
        self.recipient = (recipient or "").strip()
        self.sender = (sender or self.username).strip()
        self.timeout = timeout
        self.smtp_factory = smtp_factory

    @property
    def configured(self) -> bool:
        return bool(
            self.smtp_host
            and self.smtp_port
            and self.username
            and self.password
            and self.recipient
            and self.sender
        )

    def send(self, alerts: Iterable[AgentAlert]) -> DeliveryResult:
        items = tuple(alerts)
        if not items:
            return DeliveryResult("email", 0, 0, 0, True)
        if not self.configured:
            return DeliveryResult(
                "email",
                attempted=len(items),
                delivered=0,
                failed=0,
                skipped=True,
                errors=("Email credentials are not configured",),
            )

        message = EmailMessage()
        message["Subject"] = f"ODS opportunity alerts ({len(items)})"
        message["From"] = self.sender
        message["To"] = self.recipient
        message.set_content(format_email_digest(items))

        try:
            context = ssl.create_default_context()
            with self.smtp_factory(
                self.smtp_host,
                self.smtp_port,
                timeout=self.timeout,
                context=context,
            ) as smtp:
                smtp.login(self.username, self.password)
                smtp.send_message(message)
        except Exception as exc:
            return DeliveryResult(
                channel="email",
                attempted=len(items),
                delivered=0,
                failed=len(items),
                skipped=False,
                errors=(str(exc),),
            )

        return DeliveryResult(
            channel="email",
            attempted=len(items),
            delivered=len(items),
            failed=0,
            skipped=False,
        )


class TelegramNotifier:
    """Send alerts through Telegram Bot API.

    Retained for backward compatibility. The scheduled ODS workflow now uses email.
    """

    def __init__(
        self,
        bot_token: str | None,
        chat_id: str | None,
        *,
        timeout: float = 15.0,
        opener: Callable[..., object] = request.urlopen,
    ) -> None:
        self.bot_token = (bot_token or "").strip()
        self.chat_id = (chat_id or "").strip()
        self.timeout = timeout
        self.opener = opener

    @property
    def configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send(self, alerts: Iterable[AgentAlert]) -> DeliveryResult:
        items = tuple(alerts)
        if not items:
            return DeliveryResult("telegram", 0, 0, 0, True)
        if not self.configured:
            return DeliveryResult(
                "telegram",
                attempted=len(items),
                delivered=0,
                failed=0,
                skipped=True,
                errors=("Telegram credentials are not configured",),
            )

        delivered = 0
        errors: list[str] = []
        endpoint = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        for alert in items:
            body = parse.urlencode(
                {
                    "chat_id": self.chat_id,
                    "text": format_alert(alert),
                    "disable_web_page_preview": "true",
                }
            ).encode("utf-8")
            req = request.Request(endpoint, data=body, method="POST")
            try:
                with self.opener(req, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if not payload.get("ok"):
                    raise RuntimeError(str(payload.get("description") or "Telegram API rejected message"))
                delivered += 1
            except Exception as exc:
                errors.append(f"{alert.opportunity_id}: {exc}")

        return DeliveryResult(
            channel="telegram",
            attempted=len(items),
            delivered=delivered,
            failed=len(items) - delivered,
            skipped=False,
            errors=tuple(errors),
        )
