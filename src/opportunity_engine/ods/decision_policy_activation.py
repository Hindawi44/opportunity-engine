"""Controlled activation of staged decision-policy change sets.

This module activates only human-approved, versioned change sets that are already
staged. It records who activated the policy and when, and prevents duplicate
activation of the same target version.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .decision_policy_release import DecisionPolicyChangeSet


@dataclass(frozen=True)
class DecisionPolicyActivation:
    change_set_id: str
    rule_name: str
    previous_version: str
    active_version: str
    activated_by: str
    activated_at: datetime
    deployment_status: str = "active"

    def __post_init__(self) -> None:
        if not self.change_set_id.strip():
            raise ValueError("change_set_id must not be empty")
        if not self.rule_name.strip():
            raise ValueError("rule_name must not be empty")
        if not self.previous_version.strip() or not self.active_version.strip():
            raise ValueError("policy versions must not be empty")
        if self.previous_version == self.active_version:
            raise ValueError("active_version must differ from previous_version")
        if not self.activated_by.strip():
            raise ValueError("activated_by must not be empty")
        if self.activated_at.tzinfo is None:
            raise ValueError("activated_at must be timezone-aware")
        if self.deployment_status != "active":
            raise ValueError("activated policy must have active deployment status")


@dataclass(frozen=True)
class DecisionPolicyActivationResult:
    activation: DecisionPolicyActivation
    audit_log: tuple[str, ...]


def activate_staged_policy_change(
    change_set: DecisionPolicyChangeSet,
    *,
    activated_by: str,
    activated_at: datetime | None = None,
    existing_activations: Iterable[DecisionPolicyActivation] = (),
) -> DecisionPolicyActivationResult:
    """Activate one staged policy change with explicit human attribution."""

    if change_set.deployment_status != "staged":
        raise ValueError("only staged policy changes can be activated")
    if change_set.automatically_applied:
        raise ValueError("automatically applied policy changes cannot be activated")
    if not activated_by.strip():
        raise ValueError("activated_by must not be empty")

    now = activated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("activated_at must be timezone-aware")
    if now < change_set.staged_at:
        raise ValueError("activated_at cannot be earlier than staged_at")

    prior = tuple(existing_activations)
    if any(item.change_set_id == change_set.change_set_id for item in prior):
        raise ValueError("change set has already been activated")
    if any(
        item.rule_name == change_set.rule_name
        and item.active_version == change_set.target_version
        for item in prior
    ):
        raise ValueError("target policy version is already active for this rule")

    activation = DecisionPolicyActivation(
        change_set_id=change_set.change_set_id,
        rule_name=change_set.rule_name,
        previous_version=change_set.previous_version,
        active_version=change_set.target_version,
        activated_by=activated_by.strip(),
        activated_at=now,
    )
    audit = (
        f"Activated {change_set.change_set_id} for rule {change_set.rule_name}.",
        f"Policy version advanced from {change_set.previous_version} to {change_set.target_version}.",
        f"Activation approved by {activated_by.strip()} at {now.isoformat()}.",
    )
    return DecisionPolicyActivationResult(activation=activation, audit_log=audit)
