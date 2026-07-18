import pytest

from opportunity_engine.ods.decision import (
    ExecutiveDecision,
    ExecutiveDecisionReport,
    OpportunityDecisionResult,
)
from opportunity_engine.ods.decision_outcome import apply_decision_outcome
from opportunity_engine.ods.models import LifecycleState, OpportunityCandidate


def _opportunity(
    state: LifecycleState = LifecycleState.DECISION_CANDIDATE,
    opportunity_id: str = "opp-1",
) -> OpportunityCandidate:
    return OpportunityCandidate(
        opportunity_id=opportunity_id,
        title="Example opportunity",
        description="Decision-ready opportunity",
        category="test",
        evidence=("decision evidence",),
        confidence=0.9,
        source_plugin="test",
        lifecycle_state=state,
    )


def _result(decision: ExecutiveDecision, opportunity_id: str = "opp-1") -> OpportunityDecisionResult:
    report = ExecutiveDecisionReport(
        decision=decision,
        score=80.0,
        component_scores=(("confidence", 80.0),),
        reasons=("test",),
        blockers=(),
        missing_evidence=(),
        first_7_days=("test",),
        first_30_days=("test",),
        first_90_days=("test",),
    )
    return OpportunityDecisionResult(
        opportunity_id=opportunity_id,
        lifecycle_state=LifecycleState.DECISION_CANDIDATE,
        report=report,
    )


@pytest.mark.parametrize(
    ("decision", "expected_state"),
    (
        (ExecutiveDecision.GO, LifecycleState.EXECUTION),
        (ExecutiveDecision.WAIT, LifecycleState.MONITORING),
        (ExecutiveDecision.REJECT, LifecycleState.ARCHIVED),
    ),
)
def test_decision_maps_to_expected_terminal_state(decision, expected_state):
    advanced = apply_decision_outcome(_opportunity(), _result(decision))
    assert advanced.lifecycle_state is expected_state


def test_decision_outcome_rejects_wrong_source_lifecycle():
    with pytest.raises(ValueError, match="requires lifecycle state decision_candidate"):
        apply_decision_outcome(
            _opportunity(LifecycleState.FINANCIALLY_ASSESSED),
            _result(ExecutiveDecision.GO),
        )


def test_decision_outcome_rejects_mismatched_opportunity():
    with pytest.raises(ValueError, match="same opportunity"):
        apply_decision_outcome(
            _opportunity(opportunity_id="opp-1"),
            _result(ExecutiveDecision.GO, opportunity_id="opp-2"),
        )


def test_terminal_states_do_not_allow_further_transition():
    for state in (
        LifecycleState.EXECUTION,
        LifecycleState.MONITORING,
        LifecycleState.ARCHIVED,
    ):
        with pytest.raises(ValueError, match="invalid lifecycle transition"):
            _opportunity(state).transition_to(LifecycleState.SIGNAL)
