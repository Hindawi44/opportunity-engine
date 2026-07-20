"""Persistent, conservative alerts for high-value opportunity events."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .opportunity_discovery import OpportunityDiscoveryReport
from .opportunity_profit import OpportunityProfitDecision
from .price_history import PriceHistorySummary
from .unified_opportunity import UnifiedOpportunity


@dataclass(frozen=True)
class SmartAlertPolicy:
    minimum_discovery_score: float = 70.0
    minimum_profit_nok: float = 2_000.0
    ending_soon_hours: int = 24

    def __post_init__(self) -> None:
        if not 0 <= self.minimum_discovery_score <= 100:
            raise ValueError("minimum_discovery_score must be between 0 and 100")
        if self.minimum_profit_nok < 0:
            raise ValueError("minimum_profit_nok must not be negative")
        if self.ending_soon_hours <= 0:
            raise ValueError("ending_soon_hours must be positive")


@dataclass(frozen=True)
class SmartAlert:
    alert_id: str
    opportunity_id: str
    alert_type: str
    severity: str
    title: str
    message: str
    created_at: str
    url: str
    discovery_score: float
    expected_profit_nok: float | None
    ends_at: str | None


class SmartAlertsEngine:
    """Create new alerts once per event signature and persist sent state.

    The engine writes an outbox/state file only. Delivery through email, Telegram, or
    another channel can consume the returned alerts without changing decision logic.
    """

    def __init__(
        self,
        state_path: str | Path,
        policy: SmartAlertPolicy | None = None,
    ) -> None:
        self.state_path = Path(state_path)
        self.policy = policy or SmartAlertPolicy()
        self._state = self._load()

    def evaluate(
        self,
        opportunity: UnifiedOpportunity,
        discovery: OpportunityDiscoveryReport,
        decision: OpportunityProfitDecision,
        history: PriceHistorySummary,
        *,
        observed_at: datetime | None = None,
    ) -> tuple[SmartAlert, ...]:
        observed_at = observed_at or datetime.now(timezone.utc)
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        observed_at = observed_at.astimezone(timezone.utc)

        candidates: list[tuple[str, str, str]] = []
        if discovery.is_exceptional:
            candidates.append((
                "exceptional_opportunity",
                "critical",
                "فرصة استثنائية تحتاج مراجعة فورية",
            ))
        elif discovery.discovery_score >= self.policy.minimum_discovery_score:
            candidates.append((
                "strong_opportunity",
                "high",
                "فرصة قوية ظهرت في المحرك",
            ))

        if history.significant_drop:
            candidates.append((
                "significant_price_drop",
                "high",
                "انخفاض مهم في سعر الفرصة",
            ))

        if (
            decision.expected_profit_nok is not None
            and decision.expected_profit_nok >= self.policy.minimum_profit_nok
            and decision.decision == "buy"
        ):
            candidates.append((
                "verified_profit",
                "high",
                "ربحية متحققة تتجاوز الحد المطلوب",
            ))

        if opportunity.ends_at is not None:
            ends_at = opportunity.ends_at
            if ends_at.tzinfo is None:
                ends_at = ends_at.replace(tzinfo=timezone.utc)
            hours_left = (ends_at.astimezone(timezone.utc) - observed_at).total_seconds() / 3600
            if 0 <= hours_left <= self.policy.ending_soon_hours and discovery.requires_immediate_review:
                candidates.append((
                    "ending_soon",
                    "critical",
                    "الفرصة القوية ستنتهي قريبًا",
                ))

        alerts: list[SmartAlert] = []
        for alert_type, severity, title in candidates:
            signature = self._signature(opportunity.opportunity_id, alert_type, history, discovery)
            if signature in self._state["sent_signatures"]:
                continue
            alert = SmartAlert(
                alert_id=signature,
                opportunity_id=opportunity.opportunity_id,
                alert_type=alert_type,
                severity=severity,
                title=title,
                message=self._message(opportunity, discovery, decision, history),
                created_at=observed_at.isoformat(),
                url=opportunity.url,
                discovery_score=discovery.discovery_score,
                expected_profit_nok=decision.expected_profit_nok,
                ends_at=opportunity.ends_at.isoformat() if opportunity.ends_at else None,
            )
            alerts.append(alert)
            self._state["sent_signatures"][signature] = asdict(alert)
        return tuple(alerts)

    def save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self._state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.state_path)

    def _load(self) -> dict[str, object]:
        if not self.state_path.exists():
            return {"schema_version": 1, "sent_signatures": {}}
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Invalid smart alerts state: {self.state_path}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("sent_signatures"), dict):
            raise RuntimeError(f"Invalid smart alerts state schema: {self.state_path}")
        payload.setdefault("schema_version", 1)
        return payload

    @staticmethod
    def _signature(
        opportunity_id: str,
        alert_type: str,
        history: PriceHistorySummary,
        discovery: OpportunityDiscoveryReport,
    ) -> str:
        material = "|".join(
            (
                opportunity_id,
                alert_type,
                str(history.current_price_nok),
                str(history.price_change_count),
                str(round(discovery.discovery_score, 2)),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]

    @staticmethod
    def _message(
        opportunity: UnifiedOpportunity,
        discovery: OpportunityDiscoveryReport,
        decision: OpportunityProfitDecision,
        history: PriceHistorySummary,
    ) -> str:
        parts = [
            opportunity.title,
            f"درجة الاكتشاف: {discovery.discovery_score:.0f}/100",
            discovery.tier_label,
        ]
        if decision.expected_profit_nok is not None:
            parts.append(f"الربح المتوقع: {decision.expected_profit_nok:,.0f} كرونة")
        if history.significant_drop and history.change_from_first is not None:
            parts.append(f"تغير السعر: {history.change_from_first:.0%}")
        parts.append(discovery.suggested_action)
        return " — ".join(parts)
