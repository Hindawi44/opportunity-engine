"""Read-only governance snapshot for the decision-policy lifecycle.

The snapshot consolidates activation, monitoring, and optional rollback records into
one auditable view. It never activates, rolls back, or mutates a policy.
"""

from __future__ import annotations

from dataclasses import dataclass

from .decision_policy_activation import DecisionPolicyActivation
from .decision_policy_monitoring import PolicyEffectivenessReport
from .decision_policy_rollback import DecisionPolicyRollback


@dataclass(frozen=True)
class DecisionPolicyGovernanceSnapshot:
    change_set_id: str
    rule_name: str
    active_version: str
    lifecycle_status: str
    effectiveness_status: str
    recommendation: str
    requires_human_review: bool
    rolled_back: bool
    restored_version: str | None
    automatically_changed: bool = False

    def __post_init__(self) -> None:
        if not self.change_set_id.strip() or not self.rule_name.strip():
            raise ValueError("governance identifiers must not be empty")
        if not self.active_version.strip():
            raise ValueError("active_version must not be empty")
        if self.lifecycle_status not in {"active", "rolled_back"}:
            raise ValueError("unsupported lifecycle_status")
        if self.rolled_back != (self.lifecycle_status == "rolled_back"):
            raise ValueError("rollback state must match lifecycle_status")
        if self.rolled_back and not (self.restored_version or "").strip():
            raise ValueError("rolled-back policy requires restored_version")
        if not self.rolled_back and self.restored_version is not None:
            raise ValueError("active policy cannot expose restored_version")
        if self.automatically_changed:
            raise ValueError("governance snapshots cannot mutate policy automatically")


def build_policy_governance_snapshot(
    activation: DecisionPolicyActivation,
    report: PolicyEffectivenessReport,
    *,
    rollback: DecisionPolicyRollback | None = None,
) -> DecisionPolicyGovernanceSnapshot:
    """Build one consistent, read-only lifecycle view for a policy change set."""

    if activation.change_set_id != report.change_set_id:
        raise ValueError("activation and report must reference the same change set")
    if activation.rule_name != report.rule_name:
        raise ValueError("activation and report must reference the same rule")
    if activation.active_version != report.active_version:
        raise ValueError("monitoring report must match the active policy version")

    rolled_back = rollback is not None
    restored_version = None
    lifecycle_status = "active"

    if rollback is not None:
        if rollback.change_set_id != activation.change_set_id:
            raise ValueError("rollback must reference the same change set")
        if rollback.rule_name != activation.rule_name:
            raise ValueError("rollback must reference the same rule")
        if rollback.rolled_back_from_version != activation.active_version:
            raise ValueError("rollback source version must match activation")
        if rollback.restored_version != activation.previous_version:
            raise ValueError("rollback must restore the activation previous version")
        rolled_back = True
        restored_version = rollback.restored_version
        lifecycle_status = "rolled_back"

    return DecisionPolicyGovernanceSnapshot(
        change_set_id=activation.change_set_id,
        rule_name=activation.rule_name,
        active_version=activation.active_version,
        lifecycle_status=lifecycle_status,
        effectiveness_status=report.status.value,
        recommendation=report.recommendation,
        requires_human_review=report.requires_human_review,
        rolled_back=rolled_back,
        restored_version=restored_version,
    )
