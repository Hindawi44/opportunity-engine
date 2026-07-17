"""One-run autonomous research orchestration for grounded ODS opportunities.

The agent composes the existing live feed, evidence enrichment, and conservative
opportunity decision engine. It persists alert state and emits only meaningful changes.
Scheduling is intentionally external; one call performs one auditable research cycle.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable

from .brreg_collector import BrregSearchSlice
from .evidence_enrichment import enrich_feed
from .live_feed import LiveFeedResult, LiveOpportunityFeed
from .opportunity_decision import OpportunityDecisionReport, decide_opportunities


@dataclass(frozen=True)
class AgentAlert:
    opportunity_id: str
    title: str
    change_type: str
    decision: str
    decision_score: float
    reason: str


@dataclass(frozen=True)
class AgentRunResult:
    run_id: str
    started_at: str
    completed_at: str
    feed: LiveFeedResult
    decisions: tuple[OpportunityDecisionReport, ...]
    alerts: tuple[AgentAlert, ...]
    suppressed_count: int


class AutonomousResearchAgent:
    """Run a complete grounded research cycle and suppress duplicate alerts."""

    def __init__(
        self,
        *,
        feed_path: str | Path,
        memory_path: str | Path,
        alert_state_path: str | Path,
        run_log_path: str | Path,
        shortlist_size: int = 20,
    ) -> None:
        self.feed = LiveOpportunityFeed(feed_path, memory_path, shortlist_size=shortlist_size)
        self.alert_state_path = Path(alert_state_path)
        self.run_log_path = Path(run_log_path)

    def run(
        self,
        slices: Iterable[BrregSearchSlice],
        *,
        country: str = "Norway",
    ) -> AgentRunResult:
        started = datetime.now(timezone.utc)
        feed_result = self.feed.refresh(tuple(slices), country=country)
        active_items = tuple(item for item in feed_result.items if item.status != "REMOVED")
        decisions = decide_opportunities(enrich_feed(active_items))
        prior = self._load_alert_state()
        alerts: list[AgentAlert] = []
        suppressed = 0

        item_by_id = {item.opportunity_id: item for item in active_items}
        current_state: dict[str, dict[str, object]] = {}
        for report in decisions:
            item = item_by_id[report.opportunity_id]
            fingerprint = f"{item.status}|{report.decision.value}|{report.decision_score:.1f}"
            previous = prior.get(report.opportunity_id, {})
            previous_fingerprint = str(previous.get("fingerprint") or "")
            meaningful_change = (
                item.status in {"NEW", "UPDATED"}
                or previous_fingerprint != fingerprint
            )
            if meaningful_change:
                reason = (
                    f"Feed status is {item.status}; decision is {report.decision.value} "
                    f"at {report.decision_score:.1f}/100."
                )
                alerts.append(
                    AgentAlert(
                        opportunity_id=report.opportunity_id,
                        title=report.title,
                        change_type=item.status,
                        decision=report.decision.value,
                        decision_score=report.decision_score,
                        reason=reason,
                    )
                )
            else:
                suppressed += 1
            current_state[report.opportunity_id] = {
                "fingerprint": fingerprint,
                "title": report.title,
                "decision": report.decision.value,
                "decision_score": report.decision_score,
                "last_seen_at": item.last_seen_at,
            }

        completed = datetime.now(timezone.utc)
        result = AgentRunResult(
            run_id=f"agent-{int(started.timestamp())}",
            started_at=started.isoformat(),
            completed_at=completed.isoformat(),
            feed=feed_result,
            decisions=decisions,
            alerts=tuple(alerts),
            suppressed_count=suppressed,
        )
        self._save_alert_state(current_state)
        self._append_run_log(result)
        return result

    def _load_alert_state(self) -> dict[str, dict[str, object]]:
        if not self.alert_state_path.exists():
            return {}
        try:
            payload = json.loads(self.alert_state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Could not read agent alert state: {exc}") from exc
        records = payload.get("records", {}) if isinstance(payload, dict) else {}
        return records if isinstance(records, dict) else {}

    def _save_alert_state(self, records: dict[str, dict[str, object]]) -> None:
        self.alert_state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "records": records}
        self.alert_state_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _append_run_log(self, result: AgentRunResult) -> None:
        self.run_log_path.parent.mkdir(parents=True, exist_ok=True)
        summary = {
            "run_id": result.run_id,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            "opportunity_count": len(result.decisions),
            "alert_count": len(result.alerts),
            "suppressed_count": result.suppressed_count,
            "alerts": [asdict(alert) for alert in result.alerts],
        }
        with self.run_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(summary, ensure_ascii=False) + "\n")
