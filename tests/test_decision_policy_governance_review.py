from dataclasses import replace
from datetime import datetime, timezone

import pytest

from opportunity_engine.ods.decision_policy_governance import DecisionPolicyGovernanceSnapshot
from opportunity_engine.ods.decision_policy_governance_review import (
    DecisionPolicyGovernanceReview,
    GovernanceReviewDecision,
    review_policy_governance_snapshot,
)


UTC = timezone.utc
REVIEWED_AT = datetime(2026, 7, 19, 16, 0, tzinfo=UTC)


def _snapshot(**overrides):
    values = {
        "change_set_id": "change-1",
        "rule_name": "go_decision_thresholds",
        "active_version": "1.1.0",
        "lifecycle_status": "active",
        "effectiveness_status": "healthy",
        "recommendation": "keep_active",
        "requires_human_review": False,
        "rolled_back": False,
        "restored_version": None,
    }
    values.update(overrides)
    return DecisionPolicyGovernanceSnapshot(**values)


def test_healthy_policy_can_be_kept_active_with_audit():
    result = review_policy_governance_snapshot(
        _snapshot(),
        decision=GovernanceReviewDecision.KEEP_ACTIVE,
        reviewed_by="Mahmoud",
        notes="Performance remains healthy.",
        reviewed_at=REVIEWED_AT,
    )

    assert result.review.decision is GovernanceReviewDecision.KEEP_ACTIVE
    assert result.review.permits_automatic_change is False
    assert len(result.audit_log) == 4


def test_regression_can_authorize_rollback_review_but_not_automatic_rollback():
    snapshot = _snapshot(
        effectiveness_status="regression",
        recommendation="review_for_rollback",
        requires_human_review=True,
    )

    result = review_policy_governance_snapshot(
        snapshot,
        decision=GovernanceReviewDecision.AUTHORIZE_ROLLBACK_REVIEW,
        reviewed_by="Operations lead",
        notes="Escalate for a separate rollback decision.",
        reviewed_at=REVIEWED_AT,
    )

    assert result.review.decision.value == "authorize_rollback_review"
    assert result.review.permits_automatic_change is False


def test_rollback_review_requires_regression_recommendation():
    with pytest.raises(ValueError, match="regression recommendation"):
        review_policy_governance_snapshot(
            _snapshot(),
            decision=GovernanceReviewDecision.AUTHORIZE_ROLLBACK_REVIEW,
            reviewed_by="Mahmoud",
            notes="Not justified.",
            reviewed_at=REVIEWED_AT,
        )


def test_rolled_back_snapshot_requires_acknowledgement():
    snapshot = _snapshot(
        lifecycle_status="rolled_back",
        rolled_back=True,
        restored_version="1.0.0",
        effectiveness_status="regression",
        recommendation="review_for_rollback",
        requires_human_review=True,
    )

    with pytest.raises(ValueError, match="acknowledge_rollback"):
        review_policy_governance_snapshot(
            snapshot,
            decision=GovernanceReviewDecision.CONTINUE_MONITORING,
            reviewed_by="Mahmoud",
            notes="Wrong disposition.",
            reviewed_at=REVIEWED_AT,
        )

    result = review_policy_governance_snapshot(
        snapshot,
        decision=GovernanceReviewDecision.ACKNOWLEDGE_ROLLBACK,
        reviewed_by="Mahmoud",
        notes="Rollback record verified.",
        reviewed_at=REVIEWED_AT,
    )
    assert result.review.lifecycle_status == "rolled_back"


def test_review_rejects_duplicate_snapshot_and_naive_time():
    existing = DecisionPolicyGovernanceReview(
        change_set_id="change-1",
        rule_name="go_decision_thresholds",
        reviewed_version="1.1.0",
        lifecycle_status="active",
        decision=GovernanceReviewDecision.KEEP_ACTIVE,
        reviewed_by="Mahmoud",
        reviewed_at=REVIEWED_AT,
        notes="Already reviewed.",
    )

    with pytest.raises(ValueError, match="already been reviewed"):
        review_policy_governance_snapshot(
            _snapshot(),
            decision=GovernanceReviewDecision.KEEP_ACTIVE,
            reviewed_by="Another reviewer",
            notes="Duplicate.",
            reviewed_at=REVIEWED_AT,
            existing_reviews=(existing,),
        )

    with pytest.raises(ValueError, match="timezone-aware"):
        review_policy_governance_snapshot(
            _snapshot(),
            decision=GovernanceReviewDecision.KEEP_ACTIVE,
            reviewed_by="Mahmoud",
            notes="Naive timestamp.",
            reviewed_at=datetime(2026, 7, 19, 16, 0),
        )


def test_policy_requiring_review_cannot_be_marked_keep_active():
    snapshot = replace(
        _snapshot(),
        effectiveness_status="watch",
        recommendation="continue_monitoring",
        requires_human_review=True,
    )

    with pytest.raises(ValueError, match="cannot be kept active"):
        review_policy_governance_snapshot(
            snapshot,
            decision=GovernanceReviewDecision.KEEP_ACTIVE,
            reviewed_by="Mahmoud",
            notes="Needs review.",
            reviewed_at=REVIEWED_AT,
        )
