"""Read-only reporting for the decision-policy governance ledger.

The report summarizes immutable ledger entries without activating, rolling back, or
otherwise mutating a policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .decision_policy_governance_ledger import (
    DecisionPolicyGovernanceLedgerEntry,
    GovernanceLedgerEventType,
)


@dataclass(frozen=True)
class DecisionPolicyGovernanceLedgerReport:
    change_set_id: str
    rule_name: str
    policy_version: str
    lifecycle_status: str
    snapshot_sequence: int
    review_sequence: int | None
    review_decision: str | None
    review_actor: str | None
    pending_human_review: bool
    entry_count: int
    first_sequence: int
    last_sequence: int
    automatically_changed: bool = False

    def __post_init__(self) -> None:
        if not self.change_set_id.strip() or not self.rule_name.strip():
            raise ValueError("report identifiers must not be empty")
        if not self.policy_version.strip():
            raise ValueError("policy_version must not be empty")
        if self.lifecycle_status not in {"active", "rolled_back"}:
            raise ValueError("unsupported lifecycle_status")
        if self.snapshot_sequence < 1:
            raise ValueError("snapshot_sequence must be positive")
        if self.review_sequence is not None and self.review_sequence <= self.snapshot_sequence:
            raise ValueError("review_sequence must follow snapshot_sequence")
        if self.pending_human_review != (self.review_sequence is None):
            raise ValueError("pending review state must match review presence")
        if self.review_sequence is None and any(
            value is not None for value in (self.review_decision, self.review_actor)
        ):
            raise ValueError("pending report cannot expose review details")
        if self.review_sequence is not None and not all(
            (self.review_decision or "").strip() and (self.review_actor or "").strip()
            for _ in (0,)
        ):
            raise ValueError("reviewed report requires decision and actor")
        if self.entry_count < 1 or self.first_sequence < 1 or self.last_sequence < self.first_sequence:
            raise ValueError("invalid report sequence range")
        if self.automatically_changed:
            raise ValueError("ledger report cannot change policy automatically")


def build_governance_ledger_report(
    entries: Iterable[DecisionPolicyGovernanceLedgerEntry],
    *,
    change_set_id: str,
    policy_version: str,
) -> DecisionPolicyGovernanceLedgerReport:
    """Build one read-only report for a specific change set and policy version."""

    if not change_set_id.strip() or not policy_version.strip():
        raise ValueError("report query identifiers must not be empty")

    ledger = tuple(entries)
    _validate_ledger(ledger)
    relevant = tuple(
        entry
        for entry in ledger
        if entry.change_set_id == change_set_id and entry.policy_version == policy_version
    )
    if not relevant:
        raise ValueError("no ledger entries match the requested policy version")

    snapshots = tuple(
        entry
        for entry in relevant
        if entry.event_type is GovernanceLedgerEventType.SNAPSHOT_RECORDED
    )
    if len(snapshots) != 1:
        raise ValueError("report requires exactly one matching snapshot entry")
    snapshot = snapshots[0]

    reviews = tuple(
        entry
        for entry in relevant
        if entry.event_type is GovernanceLedgerEventType.HUMAN_REVIEW_RECORDED
    )
    if len(reviews) > 1:
        raise ValueError("report cannot contain duplicate human reviews")
    review = reviews[0] if reviews else None

    if any(entry.rule_name != snapshot.rule_name for entry in relevant):
        raise ValueError("matching ledger entries must reference the same rule")
    if any(entry.lifecycle_status != snapshot.lifecycle_status for entry in relevant):
        raise ValueError("matching ledger entries must reference the same lifecycle status")
    if review is not None and review.recorded_at < snapshot.recorded_at:
        raise ValueError("human review cannot precede its snapshot")

    return DecisionPolicyGovernanceLedgerReport(
        change_set_id=snapshot.change_set_id,
        rule_name=snapshot.rule_name,
        policy_version=snapshot.policy_version,
        lifecycle_status=snapshot.lifecycle_status,
        snapshot_sequence=snapshot.sequence,
        review_sequence=review.sequence if review else None,
        review_decision=review.decision if review else None,
        review_actor=review.actor if review else None,
        pending_human_review=review is None,
        entry_count=len(relevant),
        first_sequence=relevant[0].sequence,
        last_sequence=relevant[-1].sequence,
    )


def _validate_ledger(entries: tuple[DecisionPolicyGovernanceLedgerEntry, ...]) -> None:
    expected = tuple(range(1, len(entries) + 1))
    actual = tuple(entry.sequence for entry in entries)
    if actual != expected:
        raise ValueError("ledger entries must have contiguous sequence numbers")
    if any(later.recorded_at < earlier.recorded_at for earlier, later in zip(entries, entries[1:])):
        raise ValueError("ledger entries must be chronological")
    if any(entry.automatically_changed for entry in entries):
        raise ValueError("ledger entries cannot change policy automatically")
