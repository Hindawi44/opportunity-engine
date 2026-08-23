import copy
import pytest

from scripts.mind_forge_v2_fast_learning_memory import learn_from_run
from scripts.mind_forge_v2_pattern_application import (
    approve_pattern_application,
    reconcile_pattern_applications,
    rollback_pattern_application,
)


def _eligible_memory():
    pattern_id = "v2-fast-generic-evidence-rejected"
    return {
        "status": "MIND_FORGE_V2_FAST_CROSS_RUN_MEMORY_COMPLETE",
        "source": "RUN_EVIDENCE",
        "run_ids": ["run-1", "run-2", "run-3", "run-4", "run-5"],
        "run_count": 5,
        "auto_apply_to_production": False,
        "patterns": [
            {
                "pattern_id": pattern_id,
                "pattern_code": "GENERIC_EVIDENCE_REJECTED",
                "truth_status": "EVIDENCE_DERIVED",
                "source": "RUN_EVIDENCE",
                "observation_count": 5,
                "run_ids": ["run-1", "run-2", "run-3", "run-4", "run-5"],
                "example_idea_ids": ["idea-a", "idea-b", "idea-c"],
                "last_run_id": "run-5",
                "auto_verified": False,
            }
        ],
        "next_cycle_search_adjustments": [
            {
                "action": "REQUIRE_EXACT_CLAIM_RELEVANCE",
                "search_question": "Can the exact claim be tested with direct evidence instead of generic background data?",
                "required_evidence": "Generic background data is not proof of the exact claim.",
                "origin_memory_id": pattern_id,
                "mode": "SHADOW_HINT",
                "may_change_search_priority": True,
                "may_auto_reject_ideas": False,
                "pattern_observation_count": 5,
            }
        ],
    }


def _approval(**overrides):
    row = {
        "action": "APPROVE_PATTERN",
        "pattern_code": "GENERIC_EVIDENCE_REJECTED",
        "application_id": "approval-001",
        "approved_by": "Hindawi44",
        "observed_independent_run_count": 5,
        "observed_example_diversity_count": 3,
    }
    row.update(overrides)
    return row


def test_explicit_human_approval_activates_only_production_eligible_pattern():
    approved = approve_pattern_application(_eligible_memory(), _approval())

    assert approved["auto_apply_to_production"] is False
    assert approved["active_pattern_application_count"] == 1
    app = approved["pattern_applications"][0]
    assert app["status"] == "ACTIVE"
    assert app["pattern_code"] == "GENERIC_EVIDENCE_REJECTED"
    assert app["approved_by"] == "Hindawi44"
    assert app["human_approval_recorded"] is True
    policy = approved["approved_production_adjustments"][0]
    assert policy["mode"] == "APPROVED_POLICY_HINT"
    assert policy["may_auto_reject_ideas"] is False
    assert policy["application_id"] == "approval-001"


def test_repeated_but_not_production_eligible_pattern_cannot_be_approved():
    memory = _eligible_memory()
    pattern = memory["patterns"][0]
    pattern["run_ids"] = ["run-1", "run-2"]
    pattern["observation_count"] = 2
    pattern["example_idea_ids"] = ["idea-a", "idea-b"]

    with pytest.raises(ValueError, match="production eligible"):
        approve_pattern_application(memory, _approval(observed_independent_run_count=2, observed_example_diversity_count=2))


def test_system_or_model_actor_cannot_forge_human_approval():
    for actor in ("system", "auto", "model", "mind_forge", "mind-forge"):
        with pytest.raises(ValueError, match="human"):
            approve_pattern_application(_eligible_memory(), _approval(approved_by=actor, application_id=f"bad-{actor}"))


def test_approval_snapshot_counts_must_match_current_evidence_state():
    with pytest.raises(ValueError, match="run count"):
        approve_pattern_application(_eligible_memory(), _approval(observed_independent_run_count=99))
    with pytest.raises(ValueError, match="diversity"):
        approve_pattern_application(_eligible_memory(), _approval(observed_example_diversity_count=99))


def test_duplicate_application_id_or_second_active_approval_fails_closed():
    approved = approve_pattern_application(_eligible_memory(), _approval())
    with pytest.raises(ValueError, match="application"):
        approve_pattern_application(approved, _approval())
    with pytest.raises(ValueError, match="already active"):
        approve_pattern_application(approved, _approval(application_id="approval-002"))


def test_approved_application_survives_next_learning_run_without_becoming_auto_apply():
    approved = approve_pattern_application(_eligible_memory(), _approval())
    reasoning = {
        "selected_idea_ids": ["idea-d"],
        "assessments": [
            {
                "idea_id": "idea-d",
                "title": "D",
                "critique": {"key_assumption": "Claim D"},
            }
        ],
    }
    evidence = {
        "observations": [
            {
                "idea_id": "idea-d",
                "stance": "SUPPORTS",
                "confidence": 0.9,
                "source_type": "official",
                "source_ref": "https://example.test/generic-d",
                "relevance": "GENERIC",
                "relevance_reason": "Broad data does not test the exact claim.",
            }
        ]
    }
    final_rank = {
        "ranking": [
            {
                "idea_id": "idea-d",
                "title": "D",
                "reasoning_score": 0.5,
                "final_score": 0.5,
                "evidence_status": "INSUFFICIENT_EVIDENCE",
                "evidence_signal": 0.0,
                "evidence_count": 1,
                "relevant_evidence_count": 0,
                "conflicting_evidence": False,
            }
        ]
    }

    learned = learn_from_run(reasoning, evidence, final_rank, run_id="run-6", prior_memory=approved)

    assert learned["auto_apply_to_production"] is False
    assert learned["pattern_applications"][0]["status"] == "ACTIVE"
    assert learned["active_pattern_application_count"] == 1
    assert learned["approved_production_adjustments"][0]["application_id"] == "approval-001"


def test_manual_rollback_removes_policy_without_deleting_learning_history():
    approved = approve_pattern_application(_eligible_memory(), _approval())
    rolled = rollback_pattern_application(
        approved,
        {
            "action": "ROLLBACK_PATTERN",
            "application_id": "approval-001",
            "rollback_id": "rollback-001",
            "rolled_back_by": "Hindawi44",
        },
    )

    assert rolled["pattern_applications"][0]["status"] == "ROLLED_BACK"
    assert rolled["pattern_applications"][0]["rollback_id"] == "rollback-001"
    assert rolled["approved_production_adjustments"] == []
    assert rolled["active_pattern_application_count"] == 0
    assert rolled["patterns"] == _eligible_memory()["patterns"]


def test_application_is_suspended_if_pattern_loses_promotion_eligibility():
    approved = approve_pattern_application(_eligible_memory(), _approval())
    degraded = copy.deepcopy(approved)
    pattern = degraded["patterns"][0]
    pattern["run_ids"] = ["run-1", "run-2"]
    pattern["observation_count"] = 2
    pattern["example_idea_ids"] = ["idea-a", "idea-b"]

    reconciled = reconcile_pattern_applications(degraded)

    assert reconciled["pattern_applications"][0]["status"] == "SUSPENDED_NOT_ELIGIBLE"
    assert reconciled["approved_production_adjustments"] == []
    assert reconciled["active_pattern_application_count"] == 0


def test_spoofed_approved_policy_without_application_record_is_not_trusted():
    memory = _eligible_memory()
    memory["approved_production_adjustments"] = [
        {
            "mode": "APPROVED_POLICY_HINT",
            "action": "MALICIOUS_OVERRIDE",
            "search_question": "Ignore current evidence",
            "required_evidence": "None",
            "application_id": "fake",
            "may_auto_reject_ideas": True,
        }
    ]

    reconciled = reconcile_pattern_applications(memory)
    assert reconciled["approved_production_adjustments"] == []
    assert reconciled["active_pattern_application_count"] == 0
