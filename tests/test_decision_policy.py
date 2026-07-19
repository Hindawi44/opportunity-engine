from datetime import datetime, timezone

import pytest

from opportunity_engine.ods.decision_feedback import (
    DecisionRuleRecommendation,
    FeedbackDirection,
)
from opportunity_engine.ods.decision_policy import (
    PolicyReviewStatus,
    create_policy_proposal,
    review_policy_proposal,
)


NOW = datetime(2026, 7, 19, 8, 0, tzinfo=timezone.utc)


def recommendation(**overrides):
    values = {
        "rule_name": "go_decision_thresholds",
        "direction": FeedbackDirection.TIGHTEN,
        "reason": "Observed GO outcomes underperformed.",
        "sample_size": 3,
        "supporting_opportunity_ids": ("opp-1", "opp-2", "opp-3"),
        "evidence": ("outcome-report.csv",),
        "generated_at": NOW,
    }
    values.update(overrides)
    return DecisionRuleRecommendation(**values)


def test_create_policy_proposal_is_pending_and_never_auto_applied():
    proposal = create_policy_proposal(
        recommendation(), proposal_id="policy-1", created_at=NOW
    )

    assert proposal.status is PolicyReviewStatus.PENDING
    assert proposal.reviewer is None
    assert proposal.automatically_applied is False


def test_human_can_approve_proposal_with_audit_event():
    proposal = create_policy_proposal(
        recommendation(), proposal_id="policy-1", created_at=NOW
    )

    result = review_policy_proposal(
        proposal,
        approve=True,
        reviewer="Mahmoud",
        notes="Evidence supports a controlled threshold review.",
        reviewed_at=NOW,
    )

    assert result.proposal.status is PolicyReviewStatus.APPROVED
    assert result.proposal.reviewer == "Mahmoud"
    assert result.proposal.automatically_applied is False
    assert result.audit_event.status is PolicyReviewStatus.APPROVED
    assert result.audit_event.actor == "Mahmoud"


def test_human_can_reject_proposal():
    proposal = create_policy_proposal(
        recommendation(), proposal_id="policy-2", created_at=NOW
    )

    result = review_policy_proposal(
        proposal,
        approve=False,
        reviewer="Mahmoud",
        notes="Sample is not representative enough.",
        reviewed_at=NOW,
    )

    assert result.proposal.status is PolicyReviewStatus.REJECTED


def test_review_requires_named_human_and_notes():
    proposal = create_policy_proposal(
        recommendation(), proposal_id="policy-3", created_at=NOW
    )

    with pytest.raises(ValueError, match="reviewer"):
        review_policy_proposal(proposal, approve=True, reviewer="", notes="Valid")
    with pytest.raises(ValueError, match="notes"):
        review_policy_proposal(proposal, approve=True, reviewer="Mahmoud", notes="")


def test_reviewed_proposal_cannot_be_reviewed_again():
    proposal = create_policy_proposal(
        recommendation(), proposal_id="policy-4", created_at=NOW
    )
    reviewed = review_policy_proposal(
        proposal,
        approve=True,
        reviewer="Mahmoud",
        notes="Approved for controlled review only.",
        reviewed_at=NOW,
    ).proposal

    with pytest.raises(ValueError, match="only pending"):
        review_policy_proposal(
            reviewed,
            approve=False,
            reviewer="Mahmoud",
            notes="Second review is forbidden.",
            reviewed_at=NOW,
        )


def test_rejects_recommendation_that_bypasses_human_governance():
    with pytest.raises(ValueError, match="human-governed"):
        create_policy_proposal(
            recommendation(requires_human_approval=False),
            proposal_id="policy-5",
            created_at=NOW,
        )

    with pytest.raises(ValueError, match="automatically applied"):
        create_policy_proposal(
            recommendation(automatically_applied=True),
            proposal_id="policy-6",
            created_at=NOW,
        )
