"""Human-governed approval records for decision-rule recommendations.

This module records review decisions. It never changes executive thresholds or
applies a recommendation automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from .decision_feedback import DecisionRuleRecommendation


class PolicyReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class DecisionPolicyProposal:
    proposal_id: str
    recommendation: DecisionRuleRecommendation
    status: PolicyReviewStatus
    created_at: datetime
    reviewed_at: datetime | None = None
    reviewer: str | None = None
    review_notes: str = ""
    automatically_applied: bool = False

    def __post_init__(self) -> None:
        if not self.proposal_id.strip():
            raise ValueError("proposal_id must not be empty")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.automatically_applied:
            raise ValueError("decision policy proposals cannot be applied automatically")
        if self.status is PolicyReviewStatus.PENDING:
            if self.reviewed_at is not None or self.reviewer is not None:
                raise ValueError("pending proposals cannot contain review metadata")
        else:
            if self.reviewed_at is None or self.reviewed_at.tzinfo is None:
                raise ValueError("reviewed proposals require a timezone-aware reviewed_at")
            if not (self.reviewer or "").strip():
                raise ValueError("reviewed proposals require a human reviewer")


@dataclass(frozen=True)
class DecisionPolicyAuditEvent:
    proposal_id: str
    status: PolicyReviewStatus
    actor: str
    occurred_at: datetime
    notes: str


@dataclass(frozen=True)
class DecisionPolicyReviewResult:
    proposal: DecisionPolicyProposal
    audit_event: DecisionPolicyAuditEvent


def create_policy_proposal(
    recommendation: DecisionRuleRecommendation,
    *,
    proposal_id: str,
    created_at: datetime | None = None,
) -> DecisionPolicyProposal:
    """Register an evidence-backed recommendation for human review."""

    if not recommendation.requires_human_approval:
        raise ValueError("policy proposal requires a human-governed recommendation")
    if recommendation.automatically_applied:
        raise ValueError("automatically applied recommendations are not accepted")

    return DecisionPolicyProposal(
        proposal_id=proposal_id,
        recommendation=recommendation,
        status=PolicyReviewStatus.PENDING,
        created_at=created_at or datetime.now(timezone.utc),
    )


def review_policy_proposal(
    proposal: DecisionPolicyProposal,
    *,
    approve: bool,
    reviewer: str,
    notes: str,
    reviewed_at: datetime | None = None,
) -> DecisionPolicyReviewResult:
    """Approve or reject one pending proposal without changing live rules."""

    if proposal.status is not PolicyReviewStatus.PENDING:
        raise ValueError("only pending proposals can be reviewed")
    if not reviewer.strip():
        raise ValueError("reviewer must not be empty")
    if not notes.strip():
        raise ValueError("review notes must not be empty")

    now = reviewed_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("reviewed_at must be timezone-aware")
    status = PolicyReviewStatus.APPROVED if approve else PolicyReviewStatus.REJECTED
    reviewed = DecisionPolicyProposal(
        proposal_id=proposal.proposal_id,
        recommendation=proposal.recommendation,
        status=status,
        created_at=proposal.created_at,
        reviewed_at=now,
        reviewer=reviewer.strip(),
        review_notes=notes.strip(),
    )
    event = DecisionPolicyAuditEvent(
        proposal_id=proposal.proposal_id,
        status=status,
        actor=reviewer.strip(),
        occurred_at=now,
        notes=notes.strip(),
    )
    return DecisionPolicyReviewResult(proposal=reviewed, audit_event=event)
