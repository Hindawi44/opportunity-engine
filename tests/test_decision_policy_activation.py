from datetime import datetime, timedelta, timezone

import pytest

from opportunity_engine.ods.decision_policy_activation import (
    DecisionPolicyActivation,
    activate_staged_policy_change,
)
from opportunity_engine.ods.decision_policy_release import DecisionPolicyChangeSet


UTC = timezone.utc
STAGED_AT = datetime(2026, 7, 19, 9, 0, tzinfo=UTC)


def _change_set(**overrides):
    values = {
        "change_set_id": "change-1",
        "proposal_id": "proposal-1",
        "rule_name": "go_decision_thresholds",
        "direction": "tighten",
        "previous_version": "1.0.0",
        "target_version": "1.1.0",
        "approved_by": "Mahmoud",
        "approved_at": STAGED_AT - timedelta(hours=1),
        "staged_at": STAGED_AT,
        "review_notes": "Approved after evidence review.",
        "evidence": ("outcomes.csv",),
        "supporting_opportunity_ids": ("opp-1", "opp-2"),
    }
    values.update(overrides)
    return DecisionPolicyChangeSet(**values)


def test_activate_staged_policy_change_records_actor_version_and_audit():
    result = activate_staged_policy_change(
        _change_set(),
        activated_by="Operations lead",
        activated_at=STAGED_AT + timedelta(minutes=10),
    )

    assert result.activation.deployment_status == "active"
    assert result.activation.active_version == "1.1.0"
    assert result.activation.previous_version == "1.0.0"
    assert result.activation.activated_by == "Operations lead"
    assert len(result.audit_log) == 3


def test_activation_rejects_empty_actor_and_naive_time():
    with pytest.raises(ValueError, match="activated_by"):
        activate_staged_policy_change(_change_set(), activated_by=" ")

    with pytest.raises(ValueError, match="timezone-aware"):
        activate_staged_policy_change(
            _change_set(),
            activated_by="Reviewer",
            activated_at=datetime(2026, 7, 19, 10, 0),
        )


def test_activation_rejects_time_before_staging():
    with pytest.raises(ValueError, match="earlier than staged_at"):
        activate_staged_policy_change(
            _change_set(),
            activated_by="Reviewer",
            activated_at=STAGED_AT - timedelta(seconds=1),
        )


def test_activation_rejects_duplicate_change_set():
    existing = DecisionPolicyActivation(
        change_set_id="change-1",
        rule_name="go_decision_thresholds",
        previous_version="1.0.0",
        active_version="1.1.0",
        activated_by="Reviewer",
        activated_at=STAGED_AT + timedelta(minutes=5),
    )

    with pytest.raises(ValueError, match="already been activated"):
        activate_staged_policy_change(
            _change_set(),
            activated_by="Another reviewer",
            activated_at=STAGED_AT + timedelta(minutes=10),
            existing_activations=(existing,),
        )


def test_activation_rejects_duplicate_active_version_for_rule():
    existing = DecisionPolicyActivation(
        change_set_id="other-change",
        rule_name="go_decision_thresholds",
        previous_version="1.0.0",
        active_version="1.1.0",
        activated_by="Reviewer",
        activated_at=STAGED_AT + timedelta(minutes=5),
    )

    with pytest.raises(ValueError, match="already active"):
        activate_staged_policy_change(
            _change_set(),
            activated_by="Another reviewer",
            activated_at=STAGED_AT + timedelta(minutes=10),
            existing_activations=(existing,),
        )
