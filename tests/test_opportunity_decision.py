from __future__ import annotations

import pytest

from opportunity_engine.ods.evidence_enrichment import (
    EnrichedOpportunity,
    EvidenceBand,
    EvidenceFact,
)
from opportunity_engine.ods.live_feed import FeedItem
from opportunity_engine.ods.models import LifecycleState
from opportunity_engine.ods.opportunity_decision import (
    OpportunityDecision,
    decide_opportunities,
    decide_opportunity,
)


def _item(*, score: float = 80.0, evidence: tuple[str, ...] = ()) -> FeedItem:
    return FeedItem(
        opportunity_id="opp-1",
        title="Example opportunity",
        category="business_status_lead",
        description="Grounded opportunity lead",
        source="test",
        discovered_at="2026-07-16T00:00:00+00:00",
        last_seen_at="2026-07-16T00:00:00+00:00",
        times_seen=1,
        score=score,
        status="NEW",
        evidence=evidence,
    )


def _enriched(*, score: float = 80.0) -> EnrichedOpportunity:
    return EnrichedOpportunity(
        item=_item(score=score),
        facts=(
            EvidenceFact("Brreg", "official_status", "liquidation", 30.0),
            EvidenceFact("Market", "market_price", "NOK 100000", 25.0),
            EvidenceFact("Listing", "asset_listing", "verified listing", 20.0),
            EvidenceFact("Financial", "financials", "documented costs", 20.0),
        ),
        evidence_score=100.0,
        completeness=100.0,
        independent_sources=4,
        band=EvidenceBand.STRONG,
        missing_evidence=(),
        blockers=(),
    )


def test_brreg_only_never_produces_go() -> None:
    enriched = EnrichedOpportunity(
        item=_item(),
        facts=(
            EvidenceFact("Brreg", "official_status", "liquidation", 30.0),
            EvidenceFact("Brreg", "organisation_number", "123456789", 12.0),
            EvidenceFact("Brreg", "municipality", "NAMSOS", 8.0),
        ),
        evidence_score=50.0,
        completeness=50.0,
        independent_sources=1,
        band=EvidenceBand.PARTIAL,
        missing_evidence=(
            "Comparable market-price evidence",
            "Verified asset or inventory listing",
            "Documented costs and resale assumptions",
        ),
        blockers=("A second independent source is required before a strong recommendation",),
    )
    report = decide_opportunity(enriched)
    assert report.decision is OpportunityDecision.WATCH


def test_complete_multi_source_evidence_can_produce_go() -> None:
    report = decide_opportunity(_enriched(score=90.0))
    assert report.decision is OpportunityDecision.GO
    assert report.decision_score >= 75


def test_very_weak_lead_is_rejected() -> None:
    enriched = EnrichedOpportunity(
        item=_item(score=10.0),
        facts=(),
        evidence_score=0.0,
        completeness=0.0,
        independent_sources=0,
        band=EvidenceBand.WEAK,
        missing_evidence=("Comparable market-price evidence",),
        blockers=("No verified evidence",),
    )
    assert decide_opportunity(enriched).decision is OpportunityDecision.REJECT


def test_decision_is_blocked_before_decision_candidate() -> None:
    for state in LifecycleState:
        if state is LifecycleState.DECISION_CANDIDATE:
            continue
        with pytest.raises(ValueError, match="decision_candidate"):
            decide_opportunity(_enriched(), lifecycle_state=state)


def test_batch_decision_is_blocked_before_decision_candidate() -> None:
    with pytest.raises(ValueError, match="decision_candidate"):
        decide_opportunities((_enriched(),), lifecycle_state=LifecycleState.SIGNAL)


def test_reports_are_sorted_by_decision_then_score() -> None:
    weak = EnrichedOpportunity(
        item=_item(score=10.0),
        facts=(),
        evidence_score=0.0,
        completeness=0.0,
        independent_sources=0,
        band=EvidenceBand.WEAK,
        missing_evidence=(),
        blockers=(),
    )
    watch_item = FeedItem(**{**_item(score=70.0).__dict__, "opportunity_id": "opp-2", "title": "Watch"})
    watch = EnrichedOpportunity(
        item=watch_item,
        facts=(EvidenceFact("Brreg", "official_status", "liquidation", 30.0),),
        evidence_score=40.0,
        completeness=50.0,
        independent_sources=1,
        band=EvidenceBand.PARTIAL,
        missing_evidence=("Comparable market-price evidence",),
        blockers=(),
    )
    reports = decide_opportunities((weak, watch))
    assert reports[0].decision is OpportunityDecision.WATCH
    assert reports[1].decision is OpportunityDecision.REJECT
