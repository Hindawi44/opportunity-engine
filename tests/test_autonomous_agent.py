from __future__ import annotations

from types import SimpleNamespace

from opportunity_engine.ods.autonomous_agent import AutonomousResearchAgent
from opportunity_engine.ods.brreg_collector import BrregSearchSlice
from opportunity_engine.ods.live_feed import FeedItem
from opportunity_engine.ods.opportunity_decision import (
    OpportunityDecision,
    OpportunityDecisionReport,
)


class StubFeed:
    def __init__(self, item: FeedItem) -> None:
        self.item = item

    def refresh(self, slices, *, country="Norway"):
        assert tuple(slices)
        return SimpleNamespace(items=(self.item,), collector=SimpleNamespace(slices_failed=0))


def _item(status: str = "NEW") -> FeedItem:
    return FeedItem(
        opportunity_id="lead-1",
        title="Example AS",
        category="business_status_lead",
        description="Official status lead.",
        source="brreg_status_extractor",
        discovered_at="2026-07-17T00:00:00+00:00",
        last_seen_at="2026-07-17T00:00:00+00:00",
        times_seen=1,
        score=70.0,
        status=status,
        evidence=("official-status:liquidation",),
    )


def _report(decision: OpportunityDecision = OpportunityDecision.WATCH) -> OpportunityDecisionReport:
    return OpportunityDecisionReport(
        opportunity_id="lead-1",
        title="Example AS",
        decision=decision,
        decision_score=55.0,
        evidence_score=35.0,
        evidence_completeness=20.0,
        independent_sources=1,
        reasons=("Evidence is incomplete",),
        blockers=("More evidence required",),
        next_actions=("Collect market prices",),
    )


def test_agent_alerts_once_then_suppresses_duplicate(tmp_path, monkeypatch) -> None:
    agent = AutonomousResearchAgent(
        feed_path=tmp_path / "feed.json",
        memory_path=tmp_path / "memory.json",
        alert_state_path=tmp_path / "alerts.json",
        run_log_path=tmp_path / "runs.jsonl",
    )
    agent.feed = StubFeed(_item("NEW"))
    monkeypatch.setattr(
        "opportunity_engine.ods.autonomous_agent.enrich_feed",
        lambda items: tuple(items),
    )
    monkeypatch.setattr(
        "opportunity_engine.ods.autonomous_agent.decide_opportunities",
        lambda items: (_report(),),
    )

    first = agent.run((BrregSearchSlice("butikk"),))
    assert len(first.alerts) == 1

    agent.feed = StubFeed(_item("UNCHANGED"))
    second = agent.run((BrregSearchSlice("butikk"),))
    assert len(second.alerts) == 0
    assert second.suppressed_count == 1


def test_agent_alerts_when_decision_changes(tmp_path, monkeypatch) -> None:
    agent = AutonomousResearchAgent(
        feed_path=tmp_path / "feed.json",
        memory_path=tmp_path / "memory.json",
        alert_state_path=tmp_path / "alerts.json",
        run_log_path=tmp_path / "runs.jsonl",
    )
    agent.feed = StubFeed(_item("UNCHANGED"))
    monkeypatch.setattr(
        "opportunity_engine.ods.autonomous_agent.enrich_feed",
        lambda items: tuple(items),
    )
    monkeypatch.setattr(
        "opportunity_engine.ods.autonomous_agent.decide_opportunities",
        lambda items: (_report(OpportunityDecision.WATCH),),
    )
    agent.run((BrregSearchSlice("butikk"),))

    monkeypatch.setattr(
        "opportunity_engine.ods.autonomous_agent.decide_opportunities",
        lambda items: (_report(OpportunityDecision.REJECT),),
    )
    changed = agent.run((BrregSearchSlice("butikk"),))
    assert len(changed.alerts) == 1
    assert changed.alerts[0].decision == "REJECT"
    assert (tmp_path / "runs.jsonl").read_text(encoding="utf-8").count("\n") == 2
