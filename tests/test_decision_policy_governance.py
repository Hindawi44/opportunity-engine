from datetime import datetime, timezone

import pytest

from opportunity_engine.ods.decision_policy_activation import DecisionPolicyActivation
from opportunity_engine.ods.decision_policy_governance import build_policy_governance_snapshot
from opportunity_engine.ods.decision_policy_monitoring import (
    PolicyEffectivenessReport,
    PolicyEffectivenessStatus,
)
from opportunity_engine.ods.decision_policy_rollback import DecisionPolicyRollback


NOW = datetime(2026, 7, 19, 15, 0, tzinfo=timezone.utc)


def _activation():
    return DecisionPolicyActivation(
        change_set_id="change-1",
        rule_name="go_decision_thresholds",
        previous_version="1.0.0",
        active_version="1.1.0",
        activated_by="Mahmoud",
        activated_at=NOW,
    )


def _report(**overrides):
    values = {
        "change_set_id": "change-1",
        "rule_name": "go_decision_thresholds",
        "active_version": "1.1.0",
        "status": PolicyEffectivenessStatus.HEALTHY,
        "sample_size": 8,
        "success_rate": 0.75,
        "average_outcome_score": 0.72,
        "recommendation": "keep_active",
        "supporting_opportunity_ids": ("opp-1", "opp-2"),
        "requires_human_review": False,
    }
    values.update(overrides)
    return PolicyEffectivenessReport(**values)


def test_builds_active_governance_snapshot():
    snapshot = build_policy_governance_snapshot(_activation(), _report())

    assert snapshot.lifecycle_status == "active"
    assert snapshot.effectiveness_status == "healthy"
    assert snapshot.recommendation == "keep_active"
    assert snapshot.rolled_back is False
    assert snapshot.restored_version is None


def test_builds_rolled_back_snapshot():
    rollback = DecisionPolicyRollback(
        change_set_id="change-1",
        rule_name="go_decision_thresholds",
        rolled_back_from_version="1.1.0",
        restored_version="1.0.0",
        rolled_back_by="Mahmoud",
        rolled_back_at=NOW,
        reason="Regression confirmed.",
    )

    snapshot = build_policy_governance_snapshot(
        _activation(),
        _report(
            status=PolicyEffectivenessStatus.REGRESSION,
            recommendation="review_for_rollback",
            requires_human_review=True,
        ),
        rollback=rollback,
    )

    assert snapshot.lifecycle_status == "rolled_back"
    assert snapshot.rolled_back is True
    assert snapshot.restored_version == "1.0.0"
    assert snapshot.requires_human_review is True


def test_rejects_mismatched_monitoring_report():
    with pytest.raises(ValueError, match="same change set"):
        build_policy_governance_snapshot(
            _activation(),
            _report(change_set_id="other-change"),
        )

    with pytest.raises(ValueError, match="active policy version"):
        build_policy_governance_snapshot(
            _activation(),
            _report(active_version="2.0.0"),
        )


def test_rejects_mismatched_rollback():
    rollback = DecisionPolicyRollback(
        change_set_id="other-change",
        rule_name="go_decision_thresholds",
        rolled_back_from_version="1.1.0",
        restored_version="1.0.0",
        rolled_back_by="Mahmoud",
        rolled_back_at=NOW,
        reason="Regression confirmed.",
    )

    with pytest.raises(ValueError, match="same change set"):
        build_policy_governance_snapshot(_activation(), _report(), rollback=rollback)
