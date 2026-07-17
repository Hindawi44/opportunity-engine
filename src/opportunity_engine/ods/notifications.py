"""Optional notification delivery for meaningful ODS agent alerts."""
from __future__ import annotations

from dataclasses import dataclass
import json
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
    """Create a concise Telegram message without claiming more than the evidence supports."""
    return (
        "🔎 ODS opportunity update\n"
        f"Opportunity: {alert.title}\n"
        f"Change: {alert.change_type}\n"
        f"Decision: {alert.decision}\n"
        f"Decision score: {alert.decision_score:.1f}/100\n"
        f"Reason: {alert.reason}\n"
        f"ODS ID: {alert.opportunity_id}"
    )


class TelegramNotifier:
    """Send alerts through Telegram Bot API.

    The notifier is deliberately optional. Missing credentials produce a skipped result,
    while network/API failures are recorded per alert and do not crash the research cycle.
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
            except Exception as exc:  # isolated per alert; report without stopping the run
                errors.append(f"{alert.opportunity_id}: {exc}")

        return DeliveryResult(
            channel="telegram",
            attempted=len(items),
            delivered=delivered,
            failed=len(items) - delivered,
            skipped=False,
            errors=tuple(errors),
        )
