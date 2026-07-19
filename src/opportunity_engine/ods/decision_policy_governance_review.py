"""Human review records for decision-policy governance snapshots.

This layer records an explicit human disposition of a read-only governance snapshot.
It never activates, rolls back, or otherwise mutates a policy automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable

from .decision_policy_governance import DecisionPolicyGovernanceSnapshot


class GovernanceReviewDecision(str, Enum):
    KEEP_ACTIVE = "keep_active"
    CONTINUE_MONITORING = "continue_monitoring"
    AUTHORIZE_ROLLBACK_REVIEW = "authorize_rollback_review"
    ACKNOWLEDGE_ROLLBACK = "acknowledge_rollback"


@dataclass(frozen=True)
class DecisionPolicyGovernanceReview:
    change_set_id: str
    rule_name: str
    reviewed_version: str
    lifecycle_status: str
    decision: GovernanceReviewDecision
    reviewed_by: str
    reviewed_at: datetime
    notes: str
    permits_automatic_change: bool = False

    def __post_init__(self) -> None:
        if not self.change_set_id.strip() or not self.rule_name.strip():
            raise ValueError("governance review identifiers must not be empty")
        if not self.reviewed_version.strip():
            raise ValueError("reviewed_version must not be empty")
        if self.lifecycle_status not in {"active", "rolled_back"}:
            raise ValueError("unsupported lifecycle_status")
        if not self.reviewed_by.strip():
            raise ValueError("reviewed_by must not be empty")
        if self.reviewed_at.tzinfo is None:
            raise ValueError("reviewed_at must be timezone-aware")
        if not self.notes.strip():
            raise ValueError("review notes must not be empty")
        if self.permits_automatic_change:
            raise ValueError("governance review cannot permit automatic policy changes")


@dataclass(frozen=True)
class DecisionPolicyGovernanceReviewResult:
    review: DecisionPolicyGovernanceReview
    audit_log: tuple[str, ...]


def review_policy_governance_snapshot(
    snapshot: DecisionPolicyGovernanceSnapshot,
    *,
    decision: GovernanceReviewDecision,
    reviewed_by: str,
    notes: str,
    reviewed_at: datetime | None = None,
    existing_reviews: Iterable[DecisionPolicyGovernanceReview] = (),
) -> DecisionPolicyGovernanceReviewResult:
    """Record one explicit human disposition for a governance snapshot."""

    now = reviewed_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("reviewed_at must be timezone-aware")
    if not reviewed_by.strip():
        raise ValueError("reviewed_by must not be empty")
    if not notes.strip():
        raise ValueError("review notes must not be empty")

    prior = tuple(existing_reviews)
    if any(
        item.change_set_id == snapshot.change_set_id
        and item.reviewed_version == snapshot.active_version
        and item.lifecycle_status == snapshot.lifecycle_status
        for item in prior
    ):
        raise ValueError("governance snapshot has already been reviewed")

    if snapshot.lifecycle_status == "rolled_back":
        if decision is not GovernanceReviewDecision.ACKNOWLEDGE_ROLLBACK:
            raise ValueError("rolled-back policy requires acknowledge_rollback")
    elif decision is GovernanceReviewDecision.ACKNOWLEDGE_ROLLBACK:
        raise ValueError("active policy cannot acknowledge rollback")

    if decision is GovernanceReviewDecision.AUTHORIZE_ROLLBACK_REVIEW:
        if not snapshot.requires_human_review or snapshot.recommendation != "review_for_rollback":
            raise ValueError("rollback review requires a regression recommendation")

    if decision is GovernanceReviewDecision.KEEP_ACTIVE and snapshot.requires_human_review:
        raise ValueError("policy requiring human review cannot be kept active without review action")

    review = DecisionPolicyGovernanceReview(
        change_set_id=snapshot.change_set_id,
        rule_name=snapshot.rule_name,
        reviewed_version=snapshot.active_version,
        lifecycle_status=snapshot.lifecycle_status,
        decision=decision,
        reviewed_by=reviewed_by.strip(),
        reviewed_at=now,
        notes=notes.strip(),
    )
    audit = (
        f"Governance snapshot {snapshot.change_set_id} reviewed by {reviewed_by.strip()}.",
        f"Decision: {decision.value} for version {snapshot.active_version}.",
        f"Lifecycle status: {snapshot.lifecycle_status} at {now.isoformat()}.",
        f"Notes: {notes.strip()}",
    )
    return DecisionPolicyGovernanceReviewResult(review=review, audit_log=audit)
