from datetime import datetime, timezone

import pytest

from opportunity_engine.ods.decision_feedback import DecisionRuleRecommendation, FeedbackDirection
from opportunity_engine.ods.decision_policy import create_policy_proposal, review_policy_proposal
from opportunity_engine.ods.decision_policy_release import stage_approved_policy_change


def recommendation():
    return DecisionRuleRecommendation(
        rule_name="go_decision_thresholds",
        direction=FeedbackDirection.TIGHTEN,
        reason="Observed outcomes support review.",
        sample_size=3,
        supporting_opportunity_ids=("opp-1", "opp-2", "opp-3"),
        evidence=("report-1", "report-2"),
        generated_at=datetime(2026, 7, 19, 7, 0, tzinfo=timezone.utc),
    )


def approved_proposal():
    proposal = create_policy_proposal(
        recommendation(),
        proposal_id="proposal-1",
        created_at=datetime(2026, 7, 19, 7, 5, tzinfo=timezone.utc),
    )
    return review_policy_proposal(
        proposal,
        approve=True,
        reviewer="Mahmoud",
        notes="Approved for staged preparation.",
        reviewed_at=datetime(2026, 7, 19, 7, 10, tzinfo=timezone.utc),
    ).proposal


def test_approved_proposal_creates_versioned_staged_change():
    change = stage_approved_policy_change(
        approved_proposal(),
        change_set_id="change-1",
        previous_version="1.0.0",
        target_version="1.1.0",
        staged_at=datetime(2026, 7, 19, 7, 15, tzinfo=timezone.utc),
    )
    assert change.proposal_id == "proposal-1"
    assert change.direction == "tighten"
    assert change.deployment_status == "staged"
    assert change.automatically_applied is False


def test_pending_and_rejected_proposals_are_blocked():
    pending = create_policy_proposal(
        recommendation(),
        proposal_id="proposal-2",
        created_at=datetime(2026, 7, 19, 7, 5, tzinfo=timezone.utc),
    )
    rejected = review_policy_proposal(
        pending,
        approve=False,
        reviewer="Mahmoud",
        notes="Rejected after review.",
        reviewed_at=datetime(2026, 7, 19, 7, 10, tzinfo=timezone.utc),
    ).proposal
    for proposal in (pending, rejected):
        with pytest.raises(ValueError, match="only approved"):
            stage_approved_policy_change(
                proposal,
                change_set_id="change-x",
                previous_version="1.0.0",
                target_version="1.1.0",
            )


def test_versions_must_change_and_stage_time_follows_approval():
    approved = approved_proposal()
    with pytest.raises(ValueError, match="must differ"):
        stage_approved_policy_change(
            approved,
            change_set_id="change-2",
            previous_version="1.0.0",
            target_version="1.0.0",
        )
    with pytest.raises(ValueError, match="earlier than approval"):
        stage_approved_policy_change(
            approved,
            change_set_id="change-3",
            previous_version="1.0.0",
            target_version="1.1.0",
            staged_at=datetime(2026, 7, 19, 7, 9, tzinfo=timezone.utc),
        )
