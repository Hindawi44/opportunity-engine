"""Stage approved decision-policy proposals as versioned, auditable change sets.

This module prepares an approved proposal for a later controlled deployment. It
never mutates live decision thresholds and never marks a change as applied.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .decision_policy import DecisionPolicyProposal, PolicyReviewStatus


@dataclass(frozen=True)
class DecisionPolicyChangeSet:
    change_set_id: str
    proposal_id: str
    rule_name: str
    direction: str
    previous_version: str
    target_version: str
    approved_by: str
    approved_at: datetime
    staged_at: datetime
    review_notes: str
    evidence: tuple[str, ...]
    supporting_opportunity_ids: tuple[str, ...]
    deployment_status: str = "staged"
    automatically_applied: bool = False

    def __post_init__(self) -> None:
        if not self.change_set_id.strip():
            raise ValueError("change_set_id must not be empty")
        if not self.previous_version.strip() or not self.target_version.strip():
            raise ValueError("policy versions must not be empty")
        if self.previous_version == self.target_version:
            raise ValueError("target_version must differ from previous_version")
        if self.staged_at.tzinfo is None or self.approved_at.tzinfo is None:
            raise ValueError("policy change timestamps must be timezone-aware")
        if self.deployment_status != "staged":
            raise ValueError("new policy change sets must remain staged")
        if self.automatically_applied:
            raise ValueError("policy change sets cannot be applied automatically")
        if not self.evidence:
            raise ValueError("policy change sets require evidence")


def stage_approved_policy_change(
    proposal: DecisionPolicyProposal,
    *,
    change_set_id: str,
    previous_version: str,
    target_version: str,
    staged_at: datetime | None = None,
) -> DecisionPolicyChangeSet:
    """Create a versioned staged change only from an approved human review."""

    if proposal.status is not PolicyReviewStatus.APPROVED:
        raise ValueError("only approved policy proposals can be staged")
    if proposal.reviewed_at is None or not (proposal.reviewer or "").strip():
        raise ValueError("approved proposal requires complete human review metadata")
    if proposal.recommendation.automatically_applied:
        raise ValueError("automatically applied recommendations are not accepted")

    now = staged_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("staged_at must be timezone-aware")
    if now < proposal.reviewed_at:
        raise ValueError("staged_at cannot be earlier than approval time")

    recommendation = proposal.recommendation
    return DecisionPolicyChangeSet(
        change_set_id=change_set_id,
        proposal_id=proposal.proposal_id,
        rule_name=recommendation.rule_name,
        direction=recommendation.direction.value,
        previous_version=previous_version,
        target_version=target_version,
        approved_by=proposal.reviewer.strip(),
        approved_at=proposal.reviewed_at,
        staged_at=now,
        review_notes=proposal.review_notes,
        evidence=recommendation.evidence,
        supporting_opportunity_ids=recommendation.supporting_opportunity_ids,
    )
