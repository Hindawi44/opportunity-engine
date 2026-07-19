from datetime import datetime, timezone

import pytest

from opportunity_engine.ods.decision import ExecutiveDecision
from opportunity_engine.ods.decision_feedback import (
    DecisionOutcomeEvidence,
    FeedbackDirection,
    build_decision_feedback,
)
from opportunity_engine.ods.models import LifecycleState
from opportunity_engine.ods.outcome_learning import OutcomeLearning


def _learning(opportunity_id: str, result: str, evidence: str = "observed metric") -> OutcomeLearning:
    return OutcomeLearning(
        opportunity_id=opportunity_id,
        lifecycle_state=LifecycleState.EXECUTION,
        variance=-20.0 if result == "underperformed" else 20.0 if result == "outperformed" else 0.0,
        variance_pct=-20.0 if result == "underperformed" else 20.0 if result == "outperformed" else 0.0,
        result=result,
        lessons=("measured lesson",),
        evidence=(evidence,),
    )


def _evidence(decision: ExecutiveDecision, result: str, index: int) -> DecisionOutcomeEvidence:
    return DecisionOutcomeEvidence(
        decision=decision,
        learning=_learning(f"opp-{index}", result, f"evidence-{index}"),
    )


def test_recommends_tightening_go_rules_after_repeated_underperformance():
    report = build_decision_feedback(
        tuple(_evidence(ExecutiveDecision.GO, "underperformed", index) for index in range(3)),
        generated_at=datetime(2026, 7, 19, tzinfo=timezone.utc),
    )

    recommendation = report.recommendations[0]
    assert recommendation.rule_name == "go_decision_thresholds"
    assert recommendation.direction is FeedbackDirection.TIGHTEN
    assert recommendation.sample_size == 3
    assert recommendation.requires_human_approval is True
    assert recommendation.automatically_applied is False
    assert len(recommendation.evidence) == 3
    assert "No decision rule was changed automatically." in report.audit_log


def test_recommends_loosening_reject_rules_after_repeated_outperformance():
    report = build_decision_feedback(
        tuple(_evidence(ExecutiveDecision.REJECT, "outperformed", index) for index in range(3)),
    )

    assert report.recommendations[0].direction is FeedbackDirection.LOOSEN


def test_keeps_wait_rules_when_results_are_on_target():
    report = build_decision_feedback(
        tuple(_evidence(ExecutiveDecision.WAIT, "on_target", index) for index in range(3)),
    )

    assert report.recommendations[0].direction is FeedbackDirection.KEEP


def test_insufficient_sample_creates_no_rule_proposal():
    report = build_decision_feedback(
        (_evidence(ExecutiveDecision.GO, "underperformed", 1),),
        minimum_sample_size=3,
    )

    assert not report.recommendations
    assert any("insufficient sample" in item for item in report.audit_log)


def test_feedback_rejects_missing_outcome_evidence():
    learning = _learning("opp-1", "on_target")
    missing = OutcomeLearning(
        opportunity_id=learning.opportunity_id,
        lifecycle_state=learning.lifecycle_state,
        variance=learning.variance,
        variance_pct=learning.variance_pct,
        result=learning.result,
        lessons=learning.lessons,
        evidence=(),
    )

    with pytest.raises(ValueError, match="requires outcome evidence"):
        DecisionOutcomeEvidence(decision=ExecutiveDecision.WAIT, learning=missing)


def test_invalid_minimum_sample_and_naive_timestamp_are_rejected():
    with pytest.raises(ValueError, match="at least 1"):
        build_decision_feedback((), minimum_sample_size=0)

    with pytest.raises(ValueError, match="timezone-aware"):
        build_decision_feedback((), generated_at=datetime(2026, 7, 19))
