"""Core data contracts for the Opportunity Development System (ODS)."""

from __future__ import annotations

from dataclasses import dataclass, field
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
    """Unified opportunity contract emitted by discovery plugins."""

    opportunity_id: str
    title: str
    description: str
    category: str
    evidence: tuple[str, ...] = ()
    confidence: float = 0.0
    source_plugin: str = "unknown"

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if not self.title.strip():
            raise ValueError("title must not be empty")


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
