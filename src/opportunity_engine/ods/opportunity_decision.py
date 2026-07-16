"""Conservative decision engine for enriched live opportunities.

A GO decision is allowed only when evidence is strong, multi-source, and includes
verified asset, price, and financial evidence. Brreg status alone can never produce GO.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .evidence_enrichment import EnrichedOpportunity, EvidenceBand


class OpportunityDecision(str, Enum):
    GO = "GO"
    WATCH = "WATCH"
    REJECT = "REJECT"


@dataclass(frozen=True)
class OpportunityDecisionReport:
    opportunity_id: str
    title: str
    decision: OpportunityDecision
    decision_score: float
    evidence_score: float
    evidence_completeness: float
    independent_sources: int
    reasons: tuple[str, ...]
    blockers: tuple[str, ...]
    next_actions: tuple[str, ...]


def decide_opportunity(enriched: EnrichedOpportunity) -> OpportunityDecisionReport:
    item = enriched.item
    ranking_score = item.score if item.score is not None else 0.0
    evidence_score = enriched.evidence_score
    completeness = enriched.completeness
    sources = enriched.independent_sources

    score = round(
        0.35 * ranking_score
        + 0.40 * evidence_score
        + 0.25 * completeness,
        1,
    )

    has_market_price = any(f.kind == "market_price" for f in enriched.facts)
    has_asset_listing = any(f.kind == "asset_listing" for f in enriched.facts)
    has_financials = any(f.kind == "financials" for f in enriched.facts)
    required_for_go = has_market_price and has_asset_listing and has_financials

    reasons: list[str] = [
        f"Ranking score: {ranking_score:.1f}/100",
        f"Evidence score: {evidence_score:.1f}/100",
        f"Evidence completeness: {completeness:.1f}%",
        f"Independent sources: {sources}",
    ]
    blockers = list(enriched.blockers)

    if (
        score >= 75
        and enriched.band is EvidenceBand.STRONG
        and completeness >= 80
        and sources >= 3
        and required_for_go
    ):
        decision = OpportunityDecision.GO
        next_actions = (
            "Verify the seller or estate representative and asset ownership",
            "Confirm total acquisition, transport, tax, and handling costs",
            "Set a maximum purchase price before committing capital",
        )
    elif score < 35 or (enriched.band is EvidenceBand.WEAK and completeness < 35):
        decision = OpportunityDecision.REJECT
        reasons.append("Current evidence is too weak to justify continued priority")
        next_actions = (
            "Archive the lead unless new independent evidence appears",
            "Do not spend acquisition capital on this lead",
        )
    else:
        decision = OpportunityDecision.WATCH
        reasons.append("The lead requires additional verification before capital commitment")
        next_actions = tuple(
            action
            for missing, action in (
                ("Comparable market-price evidence", "Collect comparable used-market prices"),
                ("Verified asset or inventory listing", "Obtain a verified asset or inventory listing"),
                ("Documented costs and resale assumptions", "Document all costs and conservative resale assumptions"),
            )
            if missing in enriched.missing_evidence
        ) or ("Recheck the lead when new evidence becomes available",)

    if decision is not OpportunityDecision.GO and not blockers:
        blockers.append("GO criteria are not fully satisfied")

    return OpportunityDecisionReport(
        opportunity_id=item.opportunity_id,
        title=item.title,
        decision=decision,
        decision_score=score,
        evidence_score=evidence_score,
        evidence_completeness=completeness,
        independent_sources=sources,
        reasons=tuple(reasons),
        blockers=tuple(blockers),
        next_actions=next_actions,
    )


def decide_opportunities(
    opportunities: Iterable[EnrichedOpportunity],
) -> tuple[OpportunityDecisionReport, ...]:
    reports = [decide_opportunity(item) for item in opportunities]
    priority = {
        OpportunityDecision.GO: 0,
        OpportunityDecision.WATCH: 1,
        OpportunityDecision.REJECT: 2,
    }
    return tuple(
        sorted(
            reports,
            key=lambda report: (
                priority[report.decision],
                -report.decision_score,
                report.title.casefold(),
            ),
        )
    )
