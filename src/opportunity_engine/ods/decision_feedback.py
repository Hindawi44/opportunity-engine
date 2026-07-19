"""Convert observed decision outcomes into auditable rule-change proposals.

This module never mutates decision thresholds. It only produces evidence-backed
recommendations that require explicit human approval before any later change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable

from .decision import ExecutiveDecision
from .outcome_learning import OutcomeLearning


class FeedbackDirection(str, Enum):
    TIGHTEN = "tighten"
    LOOSEN = "loosen"
    KEEP = "keep"
    REVIEW = "review"


@dataclass(frozen=True)
class DecisionOutcomeEvidence:
    decision: ExecutiveDecision
    learning: OutcomeLearning

    def __post_init__(self) -> None:
        if not self.learning.evidence:
            raise ValueError("decision feedback requires outcome evidence")


@dataclass(frozen=True)
class DecisionRuleRecommendation:
    rule_name: str
    direction: FeedbackDirection
    reason: str
    sample_size: int
    supporting_opportunity_ids: tuple[str, ...]
    evidence: tuple[str, ...]
    generated_at: datetime
    requires_human_approval: bool = True
    automatically_applied: bool = False


@dataclass(frozen=True)
class DecisionFeedbackReport:
    recommendations: tuple[DecisionRuleRecommendation, ...]
    audit_log: tuple[str, ...]
    total_observations: int


def build_decision_feedback(
    observations: Iterable[DecisionOutcomeEvidence],
    *,
    minimum_sample_size: int = 3,
    generated_at: datetime | None = None,
) -> DecisionFeedbackReport:
    """Propose conservative rule changes without applying them automatically."""

    if minimum_sample_size < 1:
        raise ValueError("minimum_sample_size must be at least 1")

    items = tuple(observations)
    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")

    recommendations: list[DecisionRuleRecommendation] = []
    audit: list[str] = [
        f"Reviewed {len(items)} observed decision outcomes.",
        "No decision rule was changed automatically.",
    ]

    for decision in ExecutiveDecision:
        group = tuple(item for item in items if item.decision is decision)
        if len(group) < minimum_sample_size:
            audit.append(
                f"{decision.value}: insufficient sample ({len(group)}/{minimum_sample_size}); no rule proposal."
            )
            continue

        counts = {
            "outperformed": sum(item.learning.result == "outperformed" for item in group),
            "on_target": sum(item.learning.result == "on_target" for item in group),
            "underperformed": sum(item.learning.result == "underperformed" for item in group),
        }
        direction, reason = _recommendation_for(decision, counts, len(group))
        recommendation = DecisionRuleRecommendation(
            rule_name=f"{decision.value.lower()}_decision_thresholds",
            direction=direction,
            reason=reason,
            sample_size=len(group),
            supporting_opportunity_ids=tuple(
                dict.fromkeys(item.learning.opportunity_id for item in group)
            ),
            evidence=tuple(
                dict.fromkeys(evidence for item in group for evidence in item.learning.evidence)
            ),
            generated_at=now,
        )
        recommendations.append(recommendation)
        audit.append(
            f"{decision.value}: proposed {direction.value}; human approval required."
        )

    return DecisionFeedbackReport(
        recommendations=tuple(recommendations),
        audit_log=tuple(audit),
        total_observations=len(items),
    )


def _recommendation_for(
    decision: ExecutiveDecision,
    counts: dict[str, int],
    sample_size: int,
) -> tuple[FeedbackDirection, str]:
    under_rate = counts["underperformed"] / sample_size
    out_rate = counts["outperformed"] / sample_size
    target_rate = counts["on_target"] / sample_size

    if decision is ExecutiveDecision.GO:
        if under_rate >= 0.5:
            return (
                FeedbackDirection.TIGHTEN,
                "At least half of observed GO outcomes underperformed; review stricter GO thresholds.",
            )
        if out_rate >= 0.5:
            return (
                FeedbackDirection.KEEP,
                "At least half of observed GO outcomes outperformed; preserve current thresholds pending more evidence.",
            )

    if decision is ExecutiveDecision.REJECT:
        if out_rate >= 0.5:
            return (
                FeedbackDirection.LOOSEN,
                "At least half of observed REJECT outcomes later outperformed; review whether rejection thresholds are too strict.",
            )
        if under_rate >= 0.5:
            return (
                FeedbackDirection.KEEP,
                "At least half of observed REJECT outcomes underperformed; current rejection thresholds remain supported.",
            )

    if decision is ExecutiveDecision.WAIT:
        if target_rate >= 0.5:
            return (
                FeedbackDirection.KEEP,
                "At least half of observed WAIT outcomes stayed near expectations; preserve the monitoring rule.",
            )
        if under_rate >= 0.5:
            return (
                FeedbackDirection.TIGHTEN,
                "At least half of observed WAIT outcomes underperformed; review whether more cases should be rejected earlier.",
            )
        if out_rate >= 0.5:
            return (
                FeedbackDirection.LOOSEN,
                "At least half of observed WAIT outcomes outperformed; review whether strong cases can advance sooner.",
            )

    return (
        FeedbackDirection.REVIEW,
        "Observed outcomes are mixed; collect more comparable evidence before changing thresholds.",
    )
