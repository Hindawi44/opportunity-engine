from __future__ import annotations

import pytest

from opportunity_engine.opportunity_lifecycle import (
    LifecycleReasonCode,
    classify_opportunity_lifecycle,
)
from opportunity_engine.unified_models import (
    EvaluationStatus,
    ListingStatus,
    WorkflowStatus,
)


def _candidate(**overrides):
    value = {
        "listing_status": "UNKNOWN",
        "opportunity_state": "",
        "page_role": "ITEM_LISTING",
        "top5_eligible": False,
        "analysis_eligible": False,
        "verification": [],
    }
    value.update(overrides)
    return value


def test_new_record_starts_as_candidate():
    decision = classify_opportunity_lifecycle(_candidate())

    assert decision.evaluation_status == EvaluationStatus.NOT_EVALUATED
    assert decision.workflow_status == WorkflowStatus.CANDIDATE
    assert decision.reason_code == LifecycleReasonCode.NEW_CANDIDATE
    assert decision.top5_eligible is False
    assert decision.analysis_eligible is False


def test_traceable_event_is_early_signal_and_never_analysis_eligible():
    decision = classify_opportunity_lifecycle(
        _candidate(
            page_role="EVENT_LEAD",
            top5_eligible=True,
            analysis_eligible=True,
        )
    )

    assert decision.workflow_status == WorkflowStatus.EARLY_SIGNAL
    assert decision.evaluation_status == EvaluationStatus.NOT_EVALUATED
    assert decision.top5_eligible is True
    assert decision.analysis_eligible is False
    assert decision.reason_code == LifecycleReasonCode.TRACEABLE_EARLY_SIGNAL


def test_strong_lead_requires_verification():
    decision = classify_opportunity_lifecycle(
        _candidate(
            opportunity_state="STRONG_LEAD_REQUIRES_VERIFICATION",
            listing_status="ACTIVE",
            top5_eligible=True,
        )
    )

    assert decision.workflow_status == WorkflowStatus.REQUIRES_VERIFICATION
    assert decision.evaluation_status == EvaluationStatus.REQUIRES_VERIFICATION
    assert decision.top5_eligible is True
    assert decision.analysis_eligible is False


def test_non_active_strong_lead_cannot_remain_top5_eligible():
    """Regression for FINN url-id:469363853 from scheduled run 32451818613."""
    decision = classify_opportunity_lifecycle(
        _candidate(
            opportunity_state="STRONG_LEAD_REQUIRES_VERIFICATION",
            listing_status="UNKNOWN",
            top5_eligible=True,
            analysis_eligible=False,
        )
    )

    assert decision.listing_status == ListingStatus.UNKNOWN
    assert decision.workflow_status == WorkflowStatus.REQUIRES_VERIFICATION
    assert decision.evaluation_status == EvaluationStatus.REQUIRES_VERIFICATION
    assert decision.top5_eligible is False
    assert decision.analysis_eligible is False
    assert decision.reason_code == LifecycleReasonCode.MISSING_REQUIRED_VERIFICATION


def test_unverified_confirmed_sale_cannot_become_qualified():
    decision = classify_opportunity_lifecycle(
        _candidate(
            opportunity_state="CONFIRMED_SALE",
            listing_status="ACTIVE",
            top5_eligible=True,
            analysis_eligible=True,
        )
    )

    assert decision.workflow_status == WorkflowStatus.REQUIRES_VERIFICATION
    assert decision.evaluation_status == EvaluationStatus.REQUIRES_VERIFICATION
    assert decision.analysis_eligible is False
    assert decision.reason_code == LifecycleReasonCode.CONFIRMED_SALE_NEEDS_VERIFICATION


def test_verified_active_record_can_enter_active_opportunity_before_qualification():
    decision = classify_opportunity_lifecycle(
        _candidate(
            listing_status="ACTIVE",
            top5_eligible=True,
            analysis_eligible=True,
            verification=[{"verified": True}],
        )
    )

    assert decision.verified is True
    assert decision.workflow_status == WorkflowStatus.ACTIVE_OPPORTUNITY
    assert decision.evaluation_status == EvaluationStatus.NOT_EVALUATED
    assert decision.analysis_eligible is True
    assert decision.reason_code == LifecycleReasonCode.ACTIVE_READY_FOR_ANALYSIS


def test_verified_confirmed_sale_becomes_qualified():
    decision = classify_opportunity_lifecycle(
        _candidate(
            opportunity_state="CONFIRMED_SALE",
            listing_status="ACTIVE",
            top5_eligible=True,
            analysis_eligible=True,
            verification=[{"verified": True}],
        )
    )

    assert decision.workflow_status == WorkflowStatus.QUALIFIED_OPPORTUNITY
    assert decision.evaluation_status == EvaluationStatus.QUALIFIED
    assert decision.verified is True
    assert decision.analysis_eligible is True
    assert decision.reason_code == LifecycleReasonCode.QUALIFIED_CONFIRMED_SALE


def test_historical_inactive_record_is_archived_outside_current_flows():
    decision = classify_opportunity_lifecycle(
        _candidate(
            opportunity_state="HISTORICAL_MARKET_EVIDENCE",
            listing_status="ENDED",
            top5_eligible=True,
            analysis_eligible=True,
            verification=[{"verified": True}],
        )
    )

    assert decision.listing_status == ListingStatus.ENDED
    assert decision.workflow_status == WorkflowStatus.HISTORICAL_MARKET_EVIDENCE
    assert decision.evaluation_status == EvaluationStatus.HISTORICAL_ONLY
    assert decision.top5_eligible is False
    assert decision.analysis_eligible is False


@pytest.mark.parametrize("status", ["ENDED", "SOLD", "UNAVAILABLE"])
def test_inactive_listing_cannot_remain_top5_or_analysis_eligible(status: str):
    decision = classify_opportunity_lifecycle(
        _candidate(
            listing_status=status,
            top5_eligible=True,
            analysis_eligible=True,
            verification=[{"verified": True}],
        )
    )

    assert decision.workflow_status == WorkflowStatus.CLOSED
    assert decision.top5_eligible is False
    assert decision.analysis_eligible is False
    assert decision.reason_code == LifecycleReasonCode.INACTIVE_LISTING_CLOSED


def test_rejected_state_has_highest_current_flow_precedence():
    decision = classify_opportunity_lifecycle(
        _candidate(
            opportunity_state="REJECTED_NOISE",
            listing_status="ACTIVE",
            top5_eligible=True,
            analysis_eligible=True,
            verification=[{"verified": True}],
        )
    )

    assert decision.workflow_status == WorkflowStatus.REJECTED
    assert decision.evaluation_status == EvaluationStatus.REJECTED
    assert decision.top5_eligible is False
    assert decision.analysis_eligible is False
    assert decision.reason_code == LifecycleReasonCode.REJECTED_BY_SOURCE
