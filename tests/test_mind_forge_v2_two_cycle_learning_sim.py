from scripts.mind_forge_v2_learning_memory import learn_from_experiment
from scripts.mind_forge_v2_top3_research_plan import build_top3_research_plan


def _decision():
    return {
        "decision": "EXPERIMENT",
        "idea_id": "market-entry-desk",
        "title": "Norway Market-Entry Compliance Desk",
    }


def _reasoning():
    return {
        "selected_idea_ids": ["market-entry-desk", "supplier-graph", "mobile-repair"],
        "assessments": [
            {
                "idea_id": "market-entry-desk",
                "title": "Norway Market-Entry Compliance Desk",
                "critique": {"key_assumption": "Foreign small businesses have recurring costly compliance friction in Norway."},
            },
            {
                "idea_id": "supplier-graph",
                "title": "Verified Local Supplier Graph",
                "critique": {"key_assumption": "Norwegian buyers need better supplier verification signals."},
            },
            {
                "idea_id": "mobile-repair",
                "title": "Rural Mobile Repair Workshop",
                "critique": {"key_assumption": "Rural customers face material repair-access gaps."},
            },
        ],
    }


def _failed_outcome(experiment_id: str):
    return {
        "experiment_id": experiment_id,
        "idea_id": "market-entry-desk",
        "outcome": "FAILED",
        "problem_confirmations": 4,
        "concrete_commitments": 0,
        "fatal_objections": 0,
        "observations": ["Four targets described the problem, but none committed to a pilot, referral, data access, or payment."],
        "lesson": "Interest did not convert into costly action.",
    }


def test_cycle_one_failure_changes_cycle_two_search_context_without_changing_candidates_or_budget():
    baseline = build_top3_research_plan(_reasoning())
    memory = learn_from_experiment(_decision(), _failed_outcome("cycle-1"))
    adaptive = build_top3_research_plan(_reasoning(), memory)

    assert memory["latest_learning_code"] == "INTEREST_DID_NOT_CONVERT"
    assert memory["pattern_activation_state"] == "SHADOW_ONLY"
    assert memory["auto_apply_to_production"] is False

    assert [r["idea_id"] for r in adaptive["requests"]] == [r["idea_id"] for r in baseline["requests"]]
    assert adaptive["request_count"] == baseline["request_count"] == 3
    assert adaptive["max_total_search_operations"] == baseline["max_total_search_operations"] == 3
    assert adaptive["adaptive_memory_mode"] == "SHADOW_ONLY"
    assert adaptive["adaptive_hint_count"] == 1
    assert adaptive["may_auto_reject_ideas_from_memory"] is False

    hint = adaptive["requests"][0]["shadow_search_hints"][0]
    assert hint["action"] == "TEST_WILLINGNESS_BEFORE_IDEA_EXPANSION"
    assert "costly or concrete action" in hint["search_question"]
    assert "payment" in hint["required_evidence"].lower()


def test_second_independent_matching_failure_becomes_human_review_eligible_but_still_not_auto_apply():
    memory1 = learn_from_experiment(_decision(), _failed_outcome("cycle-1"))
    memory2 = learn_from_experiment(_decision(), _failed_outcome("cycle-2"), prior_memory=memory1)
    adaptive = build_top3_research_plan(_reasoning(), memory2)

    assert memory2["latest_learning_code"] == "INTEREST_DID_NOT_CONVERT"
    assert memory2["pattern_observation_count"] == 2
    assert memory2["pattern_activation_state"] == "ELIGIBLE_FOR_HUMAN_REVIEW"
    assert memory2["auto_apply_to_production"] is False
    assert adaptive["may_auto_reject_ideas_from_memory"] is False
    assert len(adaptive["requests"]) == 3
    assert adaptive["max_total_search_operations"] == 3
