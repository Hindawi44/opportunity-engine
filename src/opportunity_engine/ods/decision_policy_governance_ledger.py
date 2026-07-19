"""Append-only ledger for decision-policy governance records.

The ledger converts governance snapshots and explicit human reviews into immutable,
auditable entries. It never activates, rolls back, or changes a policy automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Iterable

from .decision_policy_governance import DecisionPolicyGovernanceSnapshot
from .decision_policy_governance_review import DecisionPolicyGovernanceReview


class GovernanceLedgerEventType(str, Enum):
    SNAPSHOT_RECORDED = "snapshot_recorded"
    HUMAN_REVIEW_RECORDED = "human_review_recorded"


@dataclass(frozen=True)
class DecisionPolicyGovernanceLedgerEntry:
    sequence: int
    change_set_id: str
    rule_name: str
    policy_version: str
    lifecycle_status: str
    event_type: GovernanceLedgerEventType
    recorded_at: datetime
    actor: str
    decision: str | None
    notes: str
    automatically_changed: bool = False

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("ledger sequence must be at least 1")
        if not self.change_set_id.strip() or not self.rule_name.strip():
            raise ValueError("ledger identifiers must not be empty")
        if not self.policy_version.strip():
            raise ValueError("policy_version must not be empty")
        if self.lifecycle_status not in {"active", "rolled_back"}:
            raise ValueError("unsupported lifecycle_status")
        if self.recorded_at.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")
        if not self.actor.strip():
            raise ValueError("actor must not be empty")
        if not self.notes.strip():
            raise ValueError("notes must not be empty")
        if self.event_type is GovernanceLedgerEventType.HUMAN_REVIEW_RECORDED:
            if not (self.decision or "").strip():
                raise ValueError("human review ledger entry requires decision")
        elif self.decision is not None:
            raise ValueError("snapshot ledger entry cannot contain decision")
        if self.automatically_changed:
            raise ValueError("governance ledger cannot change policy automatically")


def append_governance_snapshot_entry(
    snapshot: DecisionPolicyGovernanceSnapshot,
    *,
    recorded_at: datetime,
    existing_entries: Iterable[DecisionPolicyGovernanceLedgerEntry] = (),
) -> tuple[DecisionPolicyGovernanceLedgerEntry, ...]:
    """Append one read-only snapshot record to the governance ledger."""

    prior = tuple(existing_entries)
    _validate_existing_entries(prior)
    if recorded_at.tzinfo is None:
        raise ValueError("recorded_at must be timezone-aware")
    if any(
        item.change_set_id == snapshot.change_set_id
        and item.policy_version == snapshot.active_version
        and item.lifecycle_status == snapshot.lifecycle_status
        and item.event_type is GovernanceLedgerEventType.SNAPSHOT_RECORDED
        for item in prior
    ):
        raise ValueError("governance snapshot is already recorded")

    entry = DecisionPolicyGovernanceLedgerEntry(
        sequence=len(prior) + 1,
        change_set_id=snapshot.change_set_id,
        rule_name=snapshot.rule_name,
        policy_version=snapshot.active_version,
        lifecycle_status=snapshot.lifecycle_status,
        event_type=GovernanceLedgerEventType.SNAPSHOT_RECORDED,
        recorded_at=recorded_at,
        actor="system",
        decision=None,
        notes=(
            f"Effectiveness={snapshot.effectiveness_status}; "
            f"recommendation={snapshot.recommendation}."
        ),
    )
    return prior + (entry,)


def append_governance_review_entry(
    review: DecisionPolicyGovernanceReview,
    *,
    existing_entries: Iterable[DecisionPolicyGovernanceLedgerEntry],
) -> tuple[DecisionPolicyGovernanceLedgerEntry, ...]:
    """Append an explicit human governance decision after its snapshot record."""

    prior = tuple(existing_entries)
    _validate_existing_entries(prior)
    matching_snapshots = tuple(
        item
        for item in prior
        if item.change_set_id == review.change_set_id
        and item.rule_name == review.rule_name
        and item.policy_version == review.reviewed_version
        and item.lifecycle_status == review.lifecycle_status
        and item.event_type is GovernanceLedgerEventType.SNAPSHOT_RECORDED
    )
    if not matching_snapshots:
        raise ValueError("human review requires a matching recorded governance snapshot")
    if review.reviewed_at < matching_snapshots[-1].recorded_at:
        raise ValueError("human review cannot precede the recorded snapshot")
    if any(
        item.change_set_id == review.change_set_id
        and item.policy_version == review.reviewed_version
        and item.lifecycle_status == review.lifecycle_status
        and item.event_type is GovernanceLedgerEventType.HUMAN_REVIEW_RECORDED
        for item in prior
    ):
        raise ValueError("governance review is already recorded")

    entry = DecisionPolicyGovernanceLedgerEntry(
        sequence=len(prior) + 1,
        change_set_id=review.change_set_id,
        rule_name=review.rule_name,
        policy_version=review.reviewed_version,
        lifecycle_status=review.lifecycle_status,
        event_type=GovernanceLedgerEventType.HUMAN_REVIEW_RECORDED,
        recorded_at=review.reviewed_at,
        actor=review.reviewed_by,
        decision=review.decision.value,
        notes=review.notes,
    )
    return prior + (entry,)


def _validate_existing_entries(
    entries: tuple[DecisionPolicyGovernanceLedgerEntry, ...],
) -> None:
    expected = tuple(range(1, len(entries) + 1))
    actual = tuple(item.sequence for item in entries)
    if actual != expected:
        raise ValueError("existing ledger entries must have contiguous sequence numbers")
    if any(later.recorded_at < earlier.recorded_at for earlier, later in zip(entries, entries[1:])):
        raise ValueError("existing ledger entries must be chronological")
