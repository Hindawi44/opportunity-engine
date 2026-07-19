from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from opportunity_engine.ods.decision_policy_activation import DecisionPolicyActivation
from opportunity_engine.ods.decision_policy_rollback import (
    DecisionPolicyRollback,
    rollback_active_policy,
)


UTC = timezone.utc
ACTIVATED_AT = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)


def _activation(**overrides):
    values = {
        "change_set_id": "change-1",
        "rule_name": "go_decision_thresholds",
        "previous_version": "1.0.0",
        "active_version": "1.1.0",
        "activated_by": "Operations lead",
        "activated_at": ACTIVATED_AT,
    }
    values.update(overrides)
    return DecisionPolicyActivation(**values)


def test_rollback_restores_previous_version_and_records_audit():
    result = rollback_active_policy(
        _activation(),
        rolled_back_by="Mahmoud",
        reason="Observed regression after activation.",
        rolled_back_at=ACTIVATED_AT + timedelta(minutes=30),
    )

    assert result.rollback.deployment_status == "rolled_back"
    assert result.rollback.rolled_back_from_version == "1.1.0"
    assert result.rollback.restored_version == "1.0.0"
    assert result.rollback.rolled_back_by == "Mahmoud"
    assert len(result.audit_log) == 4


def test_rollback_rejects_non_active_activation():
    activation = SimpleNamespace(deployment_status="rolled_back")

    with pytest.raises(ValueError, match="only active"):
        rollback_active_policy(
            activation,
            rolled_back_by="Mahmoud",
            reason="Regression.",
        )


def test_rollback_requires_actor_reason_and_timezone_aware_time():
    with pytest.raises(ValueError, match="rolled_back_by"):
        rollback_active_policy(_activation(), rolled_back_by=" ", reason="Regression.")

    with pytest.raises(ValueError, match="reason"):
        rollback_active_policy(_activation(), rolled_back_by="Mahmoud", reason=" ")

    with pytest.raises(ValueError, match="timezone-aware"):
        rollback_active_policy(
            _activation(),
            rolled_back_by="Mahmoud",
            reason="Regression.",
            rolled_back_at=datetime(2026, 7, 19, 13, 0),
        )


def test_rollback_rejects_time_before_activation():
    with pytest.raises(ValueError, match="earlier than activated_at"):
        rollback_active_policy(
            _activation(),
            rolled_back_by="Mahmoud",
            reason="Regression.",
            rolled_back_at=ACTIVATED_AT - timedelta(seconds=1),
        )


def test_rollback_rejects_duplicate_change_set():
    existing = DecisionPolicyRollback(
        change_set_id="change-1",
        rule_name="go_decision_thresholds",
        rolled_back_from_version="1.1.0",
        restored_version="1.0.0",
        rolled_back_by="Mahmoud",
        rolled_back_at=ACTIVATED_AT + timedelta(minutes=10),
        reason="Regression.",
    )

    with pytest.raises(ValueError, match="already been rolled back"):
        rollback_active_policy(
            _activation(),
            rolled_back_by="Another reviewer",
            reason="Regression confirmed.",
            rolled_back_at=ACTIVATED_AT + timedelta(minutes=20),
            existing_rollbacks=(existing,),
        )
