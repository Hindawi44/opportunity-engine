import pytest

from scripts.mind_forge_v2_learning_memory import learn_from_experiment


def _decision():
    return {
        "idea_id": "idea-1",
        "title": "Norway Market-Entry Compliance Desk",
        "decision": "EXPERIMENT",
    }


def _outcome(**overrides):
    data = {
        "experiment_id": "exp-1",
        "idea_id": "idea-1",
        "outcome": "PASSED",
        "problem_confirmations": 4,
        "concrete_commitments": 2,
        "fatal_objections": 0,
        "observations": ["Four of five users described the problem as recurring."],
        "lesson": "Users want verified guidance before committing time or money.",
    }
    data.update(overrides)
    return data


def test_passed_experiment_creates_observed_memory_and_shadow_demand_hint():
    result = learn_from_experiment(_decision(), _outcome())
    assert result["latest_learning_code"] == "DEMAND_SIGNAL_CONFIRMED"
    assert result["records"][0]["truth_status"] == "OBSERVED"
    assert result["records"][0]["auto_verified"] is False
    assert result["auto_apply_to_production"] is False
    hint = result["next_cycle_search_adjustments"][0]
    assert hint["action"] == "PRIORITIZE_SIMILAR_PAIN_SIGNALS"
    assert hint["mode"] == "SHADOW_HINT"
    assert hint["may_change_search_priority"] is True
    assert hint["may_auto_reject_ideas"] is False
    assert result["pattern_activation_state"] == "SHADOW_ONLY"


def test_failed_problem_confirmation_teaches_next_search_to_falsify_earlier():
    result = learn_from_experiment(
        _decision(),
        _outcome(
            outcome="FAILED",
            problem_confirmations=1,
            concrete_commitments=0,
            observations=["Only one of five users reported the problem."],
        ),
    )
    assert result["latest_learning_code"] == "PROBLEM_NOT_CONFIRMED"
    assert result["next_cycle_search_adjustments"][0]["action"] == "FALSIFY_PROBLEM_EARLIER"


def test_interest_without_commitment_is_not_learned_as_demand():
    result = learn_from_experiment(
        _decision(),
        _outcome(
            outcome="FAILED",
            problem_confirmations=4,
            concrete_commitments=0,
            observations=["Users liked the idea but none accepted a pilot or meeting."],
        ),
    )
    assert result["latest_learning_code"] == "INTEREST_DID_NOT_CONVERT"
    assert result["next_cycle_search_adjustments"][0]["action"] == "TEST_WILLINGNESS_BEFORE_IDEA_EXPANSION"


def test_fatal_blocker_takes_priority_over_positive_signals():
    result = learn_from_experiment(
        _decision(),
        _outcome(fatal_objections=1, observations=["A regulatory blocker prevents the proposed delivery model."]),
    )
    assert result["latest_learning_code"] == "FATAL_BLOCKER_OBSERVED"
    assert result["next_cycle_search_adjustments"][0]["action"] == "CHECK_BLOCKER_BEFORE_GENERATION"


def test_two_independent_matching_outcomes_only_become_human_review_eligible():
    first = learn_from_experiment(_decision(), _outcome(experiment_id="exp-1"))
    second = learn_from_experiment(
        _decision(),
        _outcome(experiment_id="exp-2", observations=["A second independent test reproduced the same demand pattern."]),
        prior_memory=first,
    )
    assert second["pattern_observation_count"] == 2
    assert second["pattern_activation_state"] == "ELIGIBLE_FOR_HUMAN_REVIEW"
    assert second["auto_apply_to_production"] is False


def test_duplicate_experiment_cannot_be_counted_twice():
    first = learn_from_experiment(_decision(), _outcome(experiment_id="exp-1"))
    with pytest.raises(ValueError, match="duplicate experiment outcome"):
        learn_from_experiment(_decision(), _outcome(experiment_id="exp-1"), prior_memory=first)


def test_outcome_requires_real_observation_and_matching_experiment_decision():
    with pytest.raises(ValueError, match="at least one observation"):
        learn_from_experiment(_decision(), _outcome(observations=[]))

    wrong_decision = dict(_decision(), decision="HOLD")
    with pytest.raises(ValueError, match="requires an EXPERIMENT decision"):
        learn_from_experiment(wrong_decision, _outcome())
