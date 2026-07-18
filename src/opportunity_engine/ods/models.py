"""Core data contracts for the Opportunity Development System (ODS)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any
from uuid import uuid4


class Stage(str, Enum):
    """The fixed ODS workflow stages."""

    DISCOVERY = "discovery"
    RANKING = "ranking"
    BDNA = "bdna"
    VALIDATION = "validation"
    EXECUTION = "execution"
    LEARNING = "learning"


class Status(str, Enum):
    """Runtime state for sessions and stages."""

    WAITING = "waiting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class LifecycleState(str, Enum):
    """The mandatory maturity states for every ODS research item."""

    DOCUMENT = "document"
    SIGNAL = "signal"
    LEAD = "lead"
    VERIFIED_LEAD = "verified_lead"
    HYPOTHESIS = "hypothesis"
    VALIDATED_OPPORTUNITY = "validated_opportunity"
    FINANCIALLY_ASSESSED = "financially_assessed"
    DECISION_CANDIDATE = "decision_candidate"


_ALLOWED_LIFECYCLE_TRANSITIONS: dict[LifecycleState, frozenset[LifecycleState]] = {
    LifecycleState.DOCUMENT: frozenset({LifecycleState.SIGNAL}),
    LifecycleState.SIGNAL: frozenset({LifecycleState.LEAD}),
    LifecycleState.LEAD: frozenset({LifecycleState.VERIFIED_LEAD}),
    LifecycleState.VERIFIED_LEAD: frozenset({LifecycleState.HYPOTHESIS}),
    LifecycleState.HYPOTHESIS: frozenset({LifecycleState.VALIDATED_OPPORTUNITY}),
    LifecycleState.VALIDATED_OPPORTUNITY: frozenset({LifecycleState.FINANCIALLY_ASSESSED}),
    LifecycleState.FINANCIALLY_ASSESSED: frozenset({LifecycleState.DECISION_CANDIDATE}),
    LifecycleState.DECISION_CANDIDATE: frozenset(),
}


def can_transition_lifecycle(current: LifecycleState, target: LifecycleState) -> bool:
    """Return whether a direct lifecycle transition is permitted."""

    return target in _ALLOWED_LIFECYCLE_TRANSITIONS[current]


@dataclass(frozen=True)
class ODSRequest:
    """Normalized input accepted by ODS Core."""

    subject: str
    input_type: str = "sector"
    country: str | None = None
    goal: str = "discover_opportunities"
    constraints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.subject.strip():
            raise ValueError("subject must not be empty")
        if not self.input_type.strip():
            raise ValueError("input_type must not be empty")


@dataclass(frozen=True)
class OpportunityCandidate:
    """ODS research item with an explicit lifecycle maturity state.

    ``HYPOTHESIS`` remains the default for compatibility with the existing curated
    discovery plugins. Live-source extractors must set the state they actually prove,
    such as ``SIGNAL`` or ``LEAD``.
    """

    opportunity_id: str
    title: str
    description: str
    category: str
    evidence: tuple[str, ...] = ()
    confidence: float = 0.0
    source_plugin: str = "unknown"
    lifecycle_state: LifecycleState = LifecycleState.HYPOTHESIS

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if not self.opportunity_id.strip():
            raise ValueError("opportunity_id must not be empty")

    def transition_to(self, target: LifecycleState) -> OpportunityCandidate:
        """Return a copy at the next valid lifecycle state.

        Skipping states is prohibited. Evidence requirements for each transition are
        enforced by the workflow services that perform the transition.
        """

        if not can_transition_lifecycle(self.lifecycle_state, target):
            raise ValueError(
                f"invalid lifecycle transition: {self.lifecycle_state.value} -> {target.value}"
            )
        return replace(self, lifecycle_state=target)


@dataclass
class StageResult:
    """Result returned by one ODS plugin stage."""

    stage: Stage
    status: Status
    payload: Any = None
    evidence: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class ODSSession:
    """Auditable state for one end-to-end ODS run."""

    request: ODSRequest
    session_id: str = field(default_factory=lambda: str(uuid4()))
    status: Status = Status.WAITING
    current_stage: Stage | None = None
    results: dict[Stage, StageResult] = field(default_factory=dict)
    audit_log: list[str] = field(default_factory=list)

    def record(self, message: str) -> None:
        self.audit_log.append(message)
