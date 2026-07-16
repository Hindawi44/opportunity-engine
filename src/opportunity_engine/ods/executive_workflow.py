"""Bridge ODS analysis outputs into the executive decision engine."""
from __future__ import annotations

from dataclasses import dataclass

from .confidence import BrregEvidenceSummary, calculate_opportunity_confidence
from .decision import DecisionInputs, ExecutiveDecisionReport, build_executive_decision
from .financial import FinancialReport
from .runner import ODSAnalysisResult


@dataclass(frozen=True)
class ExecutiveWorkflowInputs:
    analysis: ODSAnalysisResult
    financial_report: FinancialReport | None = None
    evidence_quality: float | None = None
    market_health: float | None = None
    trend_confidence: float | None = None
    brreg: BrregEvidenceSummary | None = None


def build_decision_from_analysis(inputs: ExecutiveWorkflowInputs) -> ExecutiveDecisionReport:
    """Build a decision from the top ranked ODS opportunity without inventing data."""
    analysis = inputs.analysis
    if not analysis.ranked_opportunities:
        raise ValueError("analysis must contain at least one ranked opportunity")

    top = analysis.ranked_opportunities[0]
    confidence = calculate_opportunity_confidence(
        internal_score=top.final_score,
        candidate_confidence=top.opportunity.confidence,
        validation_readiness=analysis.validation.readiness_score,
        ssb_evidence_score=inputs.evidence_quality,
        market_health_score=inputs.market_health,
        trend_confidence=inputs.trend_confidence,
        brreg=inputs.brreg,
    )
    return build_executive_decision(
        DecisionInputs(
            opportunity_confidence=confidence.final_score,
            validation_readiness=analysis.validation.readiness_score,
            evidence_quality=inputs.evidence_quality,
            market_health=inputs.market_health,
            financial_report=inputs.financial_report,
        )
    )
