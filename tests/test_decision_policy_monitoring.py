from datetime import datetime, timedelta, timezone

import pytest

from opportunity_engine.ods.decision_policy_activation import DecisionPolicyActivation
from opportunity_engine.ods.decision_policy_monitoring import (
    PolicyEffectivenessObservation,
    PolicyEffectivenessStatus,
    monitor_policy_effectiveness,
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


def _observation(index, successful, score, *, version="1.1.0", minutes=1):
    return PolicyEffectivenessObservation(
        opportunity_id=f"opp-{index}",
        policy_version=version,
        observed_at=ACTIVATED_AT + timedelta(minutes=minutes + index),
        successful=successful,
        outcome_score=score,
    )


def test_monitor_reports_healthy_active_policy():
    observations = tuple(_observation(i, True, 0.8) for i in range(5))

    report = monitor_policy_effectiveness(_activation(), observations)

    assert report.status is PolicyEffectivenessStatus.HEALTHY
    assert report.recommendation == "keep_active"
    assert report.sample_size == 5
    assert report.success_rate == 1.0
    assert not report.requires_human_review
    assert not report.automatically_rolled_back


def test_monitor_flags_regression_for_human_rollback_review_only():
    observations = (
        _observation(1, True, 0.6),
        _observation(2, False, 0.2),
        _observation(3, False, 0.1),
        _observation(4, False, 0.3),
        _observation(5, False, 0.2),
    )

    report = monitor_policy_effectiveness(_activation(), observations)

    assert report.status is PolicyEffectivenessStatus.REGRESSION
    assert report.recommendation == "review_for_rollback"
    assert report.requires_human_review
    assert report.success_rate == pytest.approx(0.2)
    assert not report.automatically_rolled_back


def test_monitor_waits_for_minimum_evidence():
    report = monitor_policy_effectiveness(
        _activation(),
        (_observation(1, False, 0.1),),
        minimum_sample_size=2,
    )

    assert report.status is PolicyEffectivenessStatus.INSUFFICIENT_DATA
    assert report.recommendation == "collect_more_evidence"
    assert not report.requires_human_review


def test_monitor_ignores_wrong_version_and_pre_activation_observations():
    before_activation = PolicyEffectivenessObservation(
        opportunity_id="old",
        policy_version="1.1.0",
        observed_at=ACTIVATED_AT - timedelta(seconds=1),
        successful=False,
        outcome_score=0.0,
    )
    observations = (
        before_activation,
        _observation(1, False, 0.1, version="1.0.0"),
        _observation(2, True, 0.9),
    )

    report = monitor_policy_effectiveness(
        _activation(), observations, minimum_sample_size=1
    )

    assert report.sample_size == 1
    assert report.supporting_opportunity_ids == ("opp-2",)
    assert report.status is PolicyEffectivenessStatus.HEALTHY


def test_monitor_rejects_invalid_configuration():
    with pytest.raises(ValueError, match="minimum_sample_size"):
        monitor_policy_effectiveness(_activation(), (), minimum_sample_size=0)

    with pytest.raises(ValueError, match="thresholds"):
        monitor_policy_effectiveness(
            _activation(),
            (),
            healthy_success_rate=0.4,
            regression_success_rate=0.4,
        )


def test_observation_validates_score_and_timezone():
    with pytest.raises(ValueError, match="between 0 and 1"):
        PolicyEffectivenessObservation(
            opportunity_id="opp-1",
            policy_version="1.1.0",
            observed_at=ACTIVATED_AT,
            successful=True,
            outcome_score=1.1,
        )

    with pytest.raises(ValueError, match="timezone-aware"):
        PolicyEffectivenessObservation(
            opportunity_id="opp-1",
            policy_version="1.1.0",
            observed_at=datetime(2026, 7, 19, 12, 0),
            successful=True,
            outcome_score=0.8,
        )
