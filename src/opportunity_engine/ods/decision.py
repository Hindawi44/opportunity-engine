"""Deterministic executive decisions for ODS opportunities.

The engine combines already-computed evidence, validation, and user-entered
financial assumptions. It does not invent market facts or financial forecasts.
Only lifecycle items at ``DECISION_CANDIDATE`` may enter this engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .financial import FinancialReport
from .models import LifecycleState, OpportunityCandidate


class ExecutiveDecision(str, Enum):
    GO = "GO"
    WAIT = "WAIT"
    REJECT = "REJECT"


@dataclass(frozen=True)
class DecisionInputs:
    opportunity_confidence: float
    validation_readiness: float
    evidence_quality: float | None = None
    market_health: float | None = None
    financial_report: FinancialReport | None = None
    lifecycle_state: LifecycleState = LifecycleState.DECISION_CANDIDATE

    def __post_init__(self) -> None:
        if self.lifecycle_state is not LifecycleState.DECISION_CANDIDATE:
            raise ValueError(
                "executive decision requires lifecycle state decision_candidate; "
                f"received {self.lifecycle_state.value}"
            )
        for name, value in (
            ("opportunity_confidence", self.opportunity_confidence),
            ("validation_readiness", self.validation_readiness),
            ("evidence_quality", self.evidence_quality),
            ("market_health", self.market_health),
        ):
            if value is not None and not 0.0 <= value <= 100.0:
                raise ValueError(f"{name} must be between 0 and 100")


@dataclass(frozen=True)
class ExecutiveDecisionReport:
    decision: ExecutiveDecision
    score: float
    component_scores: tuple[tuple[str, float], ...]
    reasons: tuple[str, ...]
    blockers: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    first_7_days: tuple[str, ...]
    first_30_days: tuple[str, ...]
    first_90_days: tuple[str, ...]


def advance_decision_candidate(
    opportunity: OpportunityCandidate,
    *,
    opportunity_confidence: float,
    validation_readiness: float,
    evidence_quality: float,
    market_health: float,
    financial_report: FinancialReport,
) -> OpportunityCandidate:
    """Advance a financially assessed opportunity only when decision inputs are complete."""

    if opportunity.lifecycle_state is not LifecycleState.FINANCIALLY_ASSESSED:
        raise ValueError(
            "decision candidate advancement requires lifecycle state financially_assessed; "
            f"received {opportunity.lifecycle_state.value}"
        )

    for name, value in (
        ("opportunity_confidence", opportunity_confidence),
        ("validation_readiness", validation_readiness),
        ("evidence_quality", evidence_quality),
        ("market_health", market_health),
    ):
        if not 0.0 <= value <= 100.0:
            raise ValueError(f"{name} must be between 0 and 100")

    if not financial_report.scenarios:
        raise ValueError("decision candidate advancement requires financial scenarios")
    if not any(item.name == "base" for item in financial_report.scenarios):
        raise ValueError("decision candidate advancement requires a base financial scenario")

    return opportunity.transition_to(LifecycleState.DECISION_CANDIDATE)


def build_executive_decision(inputs: DecisionInputs) -> ExecutiveDecisionReport:
    """Create a conservative GO/WAIT/REJECT recommendation with explanations."""
    components: list[tuple[str, float, float]] = [
        ("confidence", inputs.opportunity_confidence, 0.35),
        ("validation", inputs.validation_readiness, 0.25),
    ]
    missing: list[str] = []

    if inputs.evidence_quality is None:
        missing.append("official evidence quality")
    else:
        components.append(("evidence", inputs.evidence_quality, 0.15))

    if inputs.market_health is None:
        missing.append("market health")
    else:
        components.append(("market", inputs.market_health, 0.10))

    blockers: list[str] = []
    if inputs.financial_report is None:
        missing.append("financial assumptions")
    else:
        financial_score, financial_blockers = _financial_score(inputs.financial_report)
        blockers.extend(financial_blockers)
        components.append(("financial", financial_score, 0.15))

    total_weight = sum(weight for _, _, weight in components)
    score = round(sum(value * weight for _, value, weight in components) / total_weight, 2)

    if inputs.opportunity_confidence < 45 or inputs.validation_readiness < 35:
        decision = ExecutiveDecision.REJECT
    elif blockers or missing or score < 75 or inputs.validation_readiness < 65:
        decision = ExecutiveDecision.WAIT
    else:
        decision = ExecutiveDecision.GO

    reasons = _reasons(components, decision)
    if decision is ExecutiveDecision.WAIT and missing:
        blockers.append("Complete missing evidence before committing capital.")
    if decision is ExecutiveDecision.REJECT:
        blockers.append("Current evidence does not justify further capital commitment.")

    seven, thirty, ninety = _roadmap(decision, missing)
    return ExecutiveDecisionReport(
        decision=decision,
        score=score,
        component_scores=tuple((name, round(value, 2)) for name, value, _ in components),
        reasons=reasons,
        blockers=tuple(dict.fromkeys(blockers)),
        missing_evidence=tuple(missing),
        first_7_days=seven,
        first_30_days=thirty,
        first_90_days=ninety,
    )


def _financial_score(report: FinancialReport) -> tuple[float, tuple[str, ...]]:
    base = next((item for item in report.scenarios if item.name == "base"), report.scenarios[0])
    blockers: list[str] = []
    score = 50.0
    if base.monthly_operating_profit > 0:
        score += 20.0
    else:
        blockers.append("Base financial scenario does not produce operating profit.")
        score -= 25.0
    if report.contribution_margin_pct >= 40:
        score += 15.0
    elif report.contribution_margin_pct < 20:
        blockers.append("Contribution margin is below 20%.")
        score -= 15.0
    if base.payback_months is not None:
        if base.payback_months <= 18:
            score += 15.0
        elif base.payback_months > 36:
            blockers.append("Base payback period exceeds 36 months.")
            score -= 10.0
    return max(0.0, min(100.0, score)), tuple(blockers)


def _reasons(components: list[tuple[str, float, float]], decision: ExecutiveDecision) -> tuple[str, ...]:
    labels = {
        "confidence": "Opportunity confidence",
        "validation": "Validation readiness",
        "evidence": "Official evidence quality",
        "market": "Market health",
        "financial": "Financial viability",
    }
    ordered = sorted(components, key=lambda item: item[1], reverse=True)
    reasons = [f"{labels[name]}: {value:.0f}/100" for name, value, _ in ordered[:3]]
    reasons.append(f"Executive rule outcome: {decision.value}.")
    return tuple(reasons)


def _roadmap(
    decision: ExecutiveDecision, missing: list[str]
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    if decision is ExecutiveDecision.REJECT:
        return (
            ("Document the rejection reasons and stop new spending.",),
            ("Revisit only if market or evidence conditions materially change.",),
            ("Archive the opportunity or replace it with a stronger candidate.",),
        )

    first_week = [
        "Interview at least 10 target customers or suppliers.",
        "Verify the highest-risk assumption with measurable evidence.",
    ]
    if missing:
        first_week.append("Collect the missing evidence: " + ", ".join(missing) + ".")

    first_month = (
        "Run the smallest paid or commitment-based MVP.",
        "Record conversion, margin, operating effort, and objections.",
        "Update the financial assumptions with observed values.",
    )
    first_quarter = (
        "Continue only if validation thresholds are met.",
        "Standardize the repeatable sales and delivery process.",
        "Review GO/WAIT/REJECT again before scaling capital.",
    )
    return tuple(first_week), first_month, first_quarter
