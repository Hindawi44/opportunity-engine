from __future__ import annotations

import pytest

from opportunity_engine.ods import (
    LifecycleState,
    OpportunityCandidate,
    can_transition_lifecycle,
)


def _candidate(state: LifecycleState = LifecycleState.HYPOTHESIS) -> OpportunityCandidate:
    return OpportunityCandidate(
        opportunity_id="item-1",
        title="Test research item",
        description="Lifecycle contract test.",
        category="test",
        lifecycle_state=state,
    )


def test_existing_discovery_candidates_default_to_hypothesis() -> None:
    assert _candidate().lifecycle_state is LifecycleState.HYPOTHESIS


def test_lifecycle_allows_only_the_next_direct_state() -> None:
    expected = (
        (LifecycleState.DOCUMENT, LifecycleState.SIGNAL),
        (LifecycleState.SIGNAL, LifecycleState.LEAD),
        (LifecycleState.LEAD, LifecycleState.VERIFIED_LEAD),
        (LifecycleState.VERIFIED_LEAD, LifecycleState.HYPOTHESIS),
        (LifecycleState.HYPOTHESIS, LifecycleState.VALIDATED_OPPORTUNITY),
        (LifecycleState.VALIDATED_OPPORTUNITY, LifecycleState.FINANCIALLY_ASSESSED),
        (LifecycleState.FINANCIALLY_ASSESSED, LifecycleState.DECISION_CANDIDATE),
        (LifecycleState.DECISION_CANDIDATE, LifecycleState.EXECUTION),
        (LifecycleState.DECISION_CANDIDATE, LifecycleState.MONITORING),
        (LifecycleState.DECISION_CANDIDATE, LifecycleState.ARCHIVED),
    )

    for current, target in expected:
        assert can_transition_lifecycle(current, target)


def test_lifecycle_rejects_skipping_states() -> None:
    candidate = _candidate(LifecycleState.SIGNAL)

    with pytest.raises(ValueError, match="invalid lifecycle transition"):
        candidate.transition_to(LifecycleState.VERIFIED_LEAD)


def test_transition_returns_new_immutable_candidate() -> None:
    original = _candidate(LifecycleState.LEAD)
    advanced = original.transition_to(LifecycleState.VERIFIED_LEAD)

    assert original.lifecycle_state is LifecycleState.LEAD
    assert advanced.lifecycle_state is LifecycleState.VERIFIED_LEAD
    assert advanced.opportunity_id == original.opportunity_id


def test_decision_candidate_allows_only_outcome_states() -> None:
    candidate = _candidate(LifecycleState.DECISION_CANDIDATE)
    allowed = {
        LifecycleState.EXECUTION,
        LifecycleState.MONITORING,
        LifecycleState.ARCHIVED,
    }

    for target in LifecycleState:
        if target in allowed:
            assert can_transition_lifecycle(candidate.lifecycle_state, target)
            assert candidate.transition_to(target).lifecycle_state is target
        else:
            assert not can_transition_lifecycle(candidate.lifecycle_state, target)
            with pytest.raises(ValueError, match="invalid lifecycle transition"):
                candidate.transition_to(target)


def test_outcome_states_are_terminal() -> None:
    for state in (
        LifecycleState.EXECUTION,
        LifecycleState.MONITORING,
        LifecycleState.ARCHIVED,
    ):
        candidate = _candidate(state)
        for target in LifecycleState:
            assert not can_transition_lifecycle(candidate.lifecycle_state, target)
            with pytest.raises(ValueError, match="invalid lifecycle transition"):
                candidate.transition_to(target)
