"""Controlled rollback of an active decision-policy version.

Rollback is explicit, human-attributed, and auditable. It restores only the
immediately previous version recorded by an activation and never occurs
automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .decision_policy_activation import DecisionPolicyActivation


@dataclass(frozen=True)
class DecisionPolicyRollback:
    change_set_id: str
    rule_name: str
    rolled_back_from_version: str
    restored_version: str
    rolled_back_by: str
    rolled_back_at: datetime
    reason: str
    deployment_status: str = "rolled_back"

    def __post_init__(self) -> None:
        if not self.change_set_id.strip():
            raise ValueError("change_set_id must not be empty")
        if not self.rule_name.strip():
            raise ValueError("rule_name must not be empty")
        if not self.rolled_back_from_version.strip() or not self.restored_version.strip():
            raise ValueError("policy versions must not be empty")
        if self.rolled_back_from_version == self.restored_version:
            raise ValueError("restored_version must differ from rolled_back_from_version")
        if not self.rolled_back_by.strip():
            raise ValueError("rolled_back_by must not be empty")
        if self.rolled_back_at.tzinfo is None:
            raise ValueError("rolled_back_at must be timezone-aware")
        if not self.reason.strip():
            raise ValueError("rollback reason must not be empty")
        if self.deployment_status != "rolled_back":
            raise ValueError("rollback must have rolled_back deployment status")


@dataclass(frozen=True)
class DecisionPolicyRollbackResult:
    rollback: DecisionPolicyRollback
    audit_log: tuple[str, ...]


def rollback_active_policy(
    activation: DecisionPolicyActivation,
    *,
    rolled_back_by: str,
    reason: str,
    rolled_back_at: datetime | None = None,
    existing_rollbacks: Iterable[DecisionPolicyRollback] = (),
) -> DecisionPolicyRollbackResult:
    """Restore the immediately previous version of one active policy."""

    if activation.deployment_status != "active":
        raise ValueError("only active policy versions can be rolled back")
    if not rolled_back_by.strip():
        raise ValueError("rolled_back_by must not be empty")
    if not reason.strip():
        raise ValueError("rollback reason must not be empty")

    now = rolled_back_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("rolled_back_at must be timezone-aware")
    if now < activation.activated_at:
        raise ValueError("rolled_back_at cannot be earlier than activated_at")

    prior = tuple(existing_rollbacks)
    if any(item.change_set_id == activation.change_set_id for item in prior):
        raise ValueError("change set has already been rolled back")

    rollback = DecisionPolicyRollback(
        change_set_id=activation.change_set_id,
        rule_name=activation.rule_name,
        rolled_back_from_version=activation.active_version,
        restored_version=activation.previous_version,
        rolled_back_by=rolled_back_by.strip(),
        rolled_back_at=now,
        reason=reason.strip(),
    )
    audit = (
        f"Rolled back {activation.change_set_id} for rule {activation.rule_name}.",
        f"Policy version restored from {activation.active_version} to {activation.previous_version}.",
        f"Rollback performed by {rolled_back_by.strip()} at {now.isoformat()}.",
        f"Reason: {reason.strip()}",
    )
    return DecisionPolicyRollbackResult(rollback=rollback, audit_log=audit)
