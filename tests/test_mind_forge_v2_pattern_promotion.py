import pytest

from scripts.mind_forge_v2_pattern_promotion import evaluate_pattern_promotions


def _pattern(
    *,
    code="GENERIC_EVIDENCE_REJECTED",
    run_ids=None,
    idea_ids=None,
    observation_count=None,
    truth_status="EVIDENCE_DERIVED",
    source="RUN_EVIDENCE",
):
    run_ids = list(run_ids or ["run-1"])
    idea_ids = list(idea_ids or ["idea-a"])
    if observation_count is None:
        observation_count = len(run_ids)
    return {
        "pattern_id": f"v2-fast-{code.lower()}",
        "pattern_code": code,
        "truth_status": truth_status,
        "source": source,
        "observation_count": observation_count,
        "run_ids": run_ids,
        "example_idea_ids": idea_ids,
        "auto_verified": False,
    }


def _memory(pattern):
    return {
        "status": "MIND_FORGE_V2_FAST_CROSS_RUN_MEMORY_COMPLETE",
        "source": "RUN_EVIDENCE",
        "auto_apply_to_production": False,
        "patterns": [pattern],
    }


def test_one_independent_observation_stays_shadow_only():
    result = evaluate_pattern_promotions(_memory(_pattern()))
    row = result["assessments"][0]

    assert row["stage"] == "SHADOW_ONLY"
    assert row["validated"] is False
    assert row["production_eligible"] is False
    assert result["auto_apply_to_production"] is False


def test_two_independent_observations_are_repeated_but_not_validated():
    result = evaluate_pattern_promotions(
        _memory(_pattern(run_ids=["run-1", "run-2"], idea_ids=["idea-a", "idea-b"]))
    )
    row = result["assessments"][0]

    assert row["stage"] == "REPEATED"
    assert row["independent_run_count"] == 2
    assert row["validated"] is False
    assert row["production_eligible"] is False


def test_three_independent_runs_and_two_examples_validate_pattern_but_do_not_promote():
    result = evaluate_pattern_promotions(
        _memory(
            _pattern(
                run_ids=["run-1", "run-2", "run-3"],
                idea_ids=["idea-a", "idea-b"],
            )
        )
    )
    row = result["assessments"][0]

    assert row["stage"] == "VALIDATED"
    assert row["validated"] is True
    assert row["production_eligible"] is False
    assert row["human_approval_required"] is False


def test_five_independent_runs_and_three_examples_become_production_eligible_only():
    result = evaluate_pattern_promotions(
        _memory(
            _pattern(
                run_ids=["run-1", "run-2", "run-3", "run-4", "run-5"],
                idea_ids=["idea-a", "idea-b", "idea-c"],
            )
        )
    )
    row = result["assessments"][0]

    assert row["stage"] == "PRODUCTION_ELIGIBLE"
    assert row["validated"] is True
    assert row["production_eligible"] is True
    assert row["human_approval_required"] is True
    assert result["production_eligible_pattern_codes"] == ["GENERIC_EVIDENCE_REJECTED"]
    assert result["auto_apply_to_production"] is False


def test_single_idea_repetition_cannot_validate_even_after_many_runs():
    result = evaluate_pattern_promotions(
        _memory(
            _pattern(
                run_ids=["run-1", "run-2", "run-3", "run-4", "run-5"],
                idea_ids=["idea-a"],
            )
        )
    )
    row = result["assessments"][0]

    assert row["stage"] == "DIVERSITY_BLOCKED"
    assert row["validated"] is False
    assert row["production_eligible"] is False


def test_duplicate_run_ids_or_spoofed_observation_count_fail_closed():
    result = evaluate_pattern_promotions(
        _memory(
            _pattern(
                run_ids=["run-1", "run-1", "run-2"],
                idea_ids=["idea-a", "idea-b"],
                observation_count=5,
            )
        )
    )
    row = result["assessments"][0]

    assert row["stage"] == "INTEGRITY_BLOCKED"
    assert row["production_eligible"] is False
    assert "run" in " ".join(row["blockers"]).lower() or "observation" in " ".join(row["blockers"]).lower()


def test_unknown_pattern_code_or_wrong_truth_source_is_blocked():
    unknown = evaluate_pattern_promotions(
        _memory(
            _pattern(
                code="UNREVIEWED_NEW_RULE",
                run_ids=["r1", "r2", "r3", "r4", "r5"],
                idea_ids=["a", "b", "c"],
            )
        )
    )["assessments"][0]
    wrong_truth = evaluate_pattern_promotions(
        _memory(
            _pattern(
                run_ids=["r1", "r2", "r3", "r4", "r5"],
                idea_ids=["a", "b", "c"],
                truth_status="ASSUMED",
                source="MODEL_INFERENCE",
            )
        )
    )["assessments"][0]

    assert unknown["stage"] == "UNSAFE_PATTERN_BLOCKED"
    assert wrong_truth["stage"] == "INTEGRITY_BLOCKED"
    assert unknown["production_eligible"] is False
    assert wrong_truth["production_eligible"] is False


def test_memory_that_claims_auto_apply_is_rejected():
    memory = _memory(_pattern())
    memory["auto_apply_to_production"] = True
    with pytest.raises(ValueError, match="auto-apply"):
        evaluate_pattern_promotions(memory)
