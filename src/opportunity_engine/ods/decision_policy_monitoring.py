"""Post-activation monitoring for decision-policy versions.

The monitor evaluates outcomes observed after a controlled activation. It can flag
regression for human review, but it never rolls a policy back automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Iterable

from .decision_policy_activation import DecisionPolicyActivation


class PolicyEffectivenessStatus(str, Enum):
    INSUFFICIENT_DATA = "insufficient_data"
    HEALTHY = "healthy"
    WATCH = "watch"
    REGRESSION = "regression"


@dataclass(frozen=True)
class PolicyEffectivenessObservation:
    opportunity_id: str
    policy_version: str
    observed_at: datetime
    successful: bool
    outcome_score: float

    def __post_init__(self) -> None:
        if not self.opportunity_id.strip():
            raise ValueError("opportunity_id must not be empty")
        if not self.policy_version.strip():
            raise ValueError("policy_version must not be empty")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not 0.0 <= self.outcome_score <= 1.0:
            raise ValueError("outcome_score must be between 0 and 1")


@dataclass(frozen=True)
class PolicyEffectivenessReport:
    change_set_id: str
    rule_name: str
    active_version: str
    status: PolicyEffectivenessStatus
    sample_size: int
    success_rate: float
    average_outcome_score: float
    recommendation: str
    supporting_opportunity_ids: tuple[str, ...]
    requires_human_review: bool
    automatically_rolled_back: bool = False

    def __post_init__(self) -> None:
        if self.automatically_rolled_back:
            raise ValueError("policy monitoring cannot roll back automatically")


def monitor_policy_effectiveness(
    activation: DecisionPolicyActivation,
    observations: Iterable[PolicyEffectivenessObservation],
    *,
    minimum_sample_size: int = 5,
    healthy_success_rate: float = 0.70,
    regression_success_rate: float = 0.40,
) -> PolicyEffectivenessReport:
    """Assess one active version and emit a human-governed recommendation."""

    if activation.deployment_status != "active":
        raise ValueError("only active policy versions can be monitored")
    if minimum_sample_size < 1:
        raise ValueError("minimum_sample_size must be at least 1")
    if not 0.0 <= regression_success_rate < healthy_success_rate <= 1.0:
        raise ValueError("effectiveness thresholds are invalid")

    relevant = tuple(
        item
        for item in observations
        if item.policy_version == activation.active_version
        and item.observed_at >= activation.activated_at
    )
    sample_size = len(relevant)
    success_rate = (
        sum(1 for item in relevant if item.successful) / sample_size
        if sample_size
        else 0.0
    )
    average_score = (
        sum(item.outcome_score for item in relevant) / sample_size
        if sample_size
        else 0.0
    )

    if sample_size < minimum_sample_size:
        status = PolicyEffectivenessStatus.INSUFFICIENT_DATA
        recommendation = "collect_more_evidence"
        requires_review = False
    elif success_rate >= healthy_success_rate:
        status = PolicyEffectivenessStatus.HEALTHY
        recommendation = "keep_active"
        requires_review = False
    elif success_rate < regression_success_rate:
        status = PolicyEffectivenessStatus.REGRESSION
        recommendation = "review_for_rollback"
        requires_review = True
    else:
        status = PolicyEffectivenessStatus.WATCH
        recommendation = "continue_monitoring"
        requires_review = True

    return PolicyEffectivenessReport(
        change_set_id=activation.change_set_id,
        rule_name=activation.rule_name,
        active_version=activation.active_version,
        status=status,
        sample_size=sample_size,
        success_rate=success_rate,
        average_outcome_score=average_score,
        recommendation=recommendation,
        supporting_opportunity_ids=tuple(item.opportunity_id for item in relevant),
        requires_human_review=requires_review,
    )
