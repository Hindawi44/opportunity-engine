from datetime import datetime, timezone

import pytest

from opportunity_engine.ods.models import LifecycleState, OpportunityCandidate
from opportunity_engine.ods.outcome_learning import learn_from_outcome, record_outcome


def _opportunity(state: LifecycleState) -> OpportunityCandidate:
    return OpportunityCandidate(
        opportunity_id="opp-1",
        title="Outcome test",
        description="Terminal opportunity",
        category="test",
        evidence=("decision evidence",),
        confidence=0.9,
        source_plugin="test",
        lifecycle_state=state,
    )


@pytest.mark.parametrize(
    "state",
    (LifecycleState.EXECUTION, LifecycleState.MONITORING, LifecycleState.ARCHIVED),
)
def test_terminal_states_can_record_outcomes(state):
    observation = record_outcome(
        _opportunity(state),
        expected_value=100,
        actual_value=110,
        evidence=("invoice-1",),
        observed_at=datetime(2026, 7, 18, tzinfo=timezone.utc),
    )

    assert observation.opportunity_id == "opp-1"
    assert observation.lifecycle_state is state


def test_non_terminal_state_cannot_record_outcome():
    with pytest.raises(ValueError, match="terminal lifecycle state"):
        record_outcome(
            _opportunity(LifecycleState.DECISION_CANDIDATE),
            expected_value=100,
            actual_value=90,
            evidence=("measurement",),
        )


def test_outcome_requires_evidence():
    with pytest.raises(ValueError, match="requires evidence"):
        record_outcome(
            _opportunity(LifecycleState.EXECUTION),
            expected_value=100,
            actual_value=90,
            evidence=(),
        )


def test_underperformance_creates_conservative_learning():
    observation = record_outcome(
        _opportunity(LifecycleState.EXECUTION),
        expected_value=100,
        actual_value=70,
        evidence=("sales report",),
    )

    learning = learn_from_outcome(observation)

    assert learning.result == "underperformed"
    assert learning.variance == -30
    assert learning.variance_pct == -30
    assert any("Do not scale" in lesson for lesson in learning.lessons)


def test_archived_outcome_remains_archived_without_new_evidence():
    observation = record_outcome(
        _opportunity(LifecycleState.ARCHIVED),
        expected_value=0,
        actual_value=0,
        evidence=("rejection review",),
    )

    learning = learn_from_outcome(observation)

    assert learning.result == "on_target"
    assert learning.variance_pct is None
    assert "Keep the opportunity archived" in learning.lessons[0]
