"""Record observed outcomes and convert them into auditable ODS learning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .models import LifecycleState, OpportunityCandidate


TERMINAL_STATES = frozenset(
    {
        LifecycleState.EXECUTION,
        LifecycleState.MONITORING,
        LifecycleState.ARCHIVED,
    }
)


@dataclass(frozen=True)
class OutcomeObservation:
    opportunity_id: str
    lifecycle_state: LifecycleState
    observed_at: datetime
    expected_value: float
    actual_value: float
    evidence: tuple[str, ...]
    notes: str = ""

    def __post_init__(self) -> None:
        if self.lifecycle_state not in TERMINAL_STATES:
            raise ValueError("outcome observation requires a terminal lifecycle state")
        if not self.opportunity_id.strip():
            raise ValueError("opportunity_id must not be empty")
        if not self.evidence:
            raise ValueError("outcome observation requires evidence")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")


@dataclass(frozen=True)
class OutcomeLearning:
    opportunity_id: str
    lifecycle_state: LifecycleState
    variance: float
    variance_pct: float | None
    result: str
    lessons: tuple[str, ...]
    evidence: tuple[str, ...]


def record_outcome(
    opportunity: OpportunityCandidate,
    *,
    expected_value: float,
    actual_value: float,
    evidence: tuple[str, ...],
    notes: str = "",
    observed_at: datetime | None = None,
) -> OutcomeObservation:
    """Create an observation only for a terminal opportunity and real evidence."""

    if opportunity.lifecycle_state not in TERMINAL_STATES:
        raise ValueError("outcome recording requires a terminal lifecycle state")

    return OutcomeObservation(
        opportunity_id=opportunity.opportunity_id,
        lifecycle_state=opportunity.lifecycle_state,
        observed_at=observed_at or datetime.now(timezone.utc),
        expected_value=expected_value,
        actual_value=actual_value,
        evidence=tuple(evidence),
        notes=notes.strip(),
    )


def learn_from_outcome(observation: OutcomeObservation) -> OutcomeLearning:
    """Produce deterministic learning without inventing causes or market facts."""

    variance = observation.actual_value - observation.expected_value
    variance_pct = None
    if observation.expected_value != 0:
        variance_pct = round((variance / abs(observation.expected_value)) * 100.0, 2)

    tolerance = max(abs(observation.expected_value) * 0.10, 1e-9)
    if variance > tolerance:
        result = "outperformed"
        lessons = (
            "Preserve the assumptions and operating actions supported by the evidence.",
            "Revalidate the result before increasing committed capital.",
        )
    elif variance < -tolerance:
        result = "underperformed"
        lessons = (
            "Review the largest assumption gap using the attached evidence.",
            "Do not scale until the negative variance is explained and retested.",
        )
    else:
        result = "on_target"
        lessons = (
            "Keep the current operating assumptions under observation.",
            "Collect another comparable outcome before changing the model.",
        )

    if observation.lifecycle_state is LifecycleState.ARCHIVED:
        lessons = (
            "Keep the opportunity archived unless new measurable evidence changes the case.",
        ) + lessons

    return OutcomeLearning(
        opportunity_id=observation.opportunity_id,
        lifecycle_state=observation.lifecycle_state,
        variance=round(variance, 2),
        variance_pct=variance_pct,
        result=result,
        lessons=lessons,
        evidence=observation.evidence,
    )
