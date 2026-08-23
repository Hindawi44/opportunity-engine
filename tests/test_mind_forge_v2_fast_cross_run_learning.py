import pytest

from scripts.mind_forge_v2_fast_learning_memory import learn_from_run
from scripts.mind_forge_v2_top3_research_plan import build_top3_research_plan


def _reasoning():
    return {
        "selected_idea_ids": ["a", "b", "c"],
        "assessments": [
            {"idea_id": "a", "title": "A", "critique": {"key_assumption": "Organizations have recurring repair needs."}},
            {"idea_id": "b", "title": "B", "critique": {"key_assumption": "Customers will consolidate pickup."}},
            {"idea_id": "c", "title": "C", "critique": {"key_assumption": "Customers accept reinforcement."}},
        ],
    }


def _evidence():
    return {
        "observations": [
            {
                "idea_id": "a",
                "stance": "SUPPORTS",
                "confidence": 0.88,
                "source_type": "official",
                "source_ref": "https://example.test/direct",
                "relevance": "DIRECT",
                "relevance_reason": "The source directly describes recurring uniform repair purchasing.",
            },
            {
                "idea_id": "b",
                "stance": "SUPPORTS",
                "confidence": 0.90,
                "source_type": "official",
                "source_ref": "https://example.test/generic",
                "relevance": "GENERIC",
                "relevance_reason": "Sector turnover does not test route clustering.",
            },
            {
                "idea_id": "c",
                "stance": "CONTRADICTS",
                "confidence": 0.80,
                "source_type": "primary",
                "source_ref": "https://example.test/adjacent",
                "relevance": "ADJACENT",
                "relevance_reason": "Related garment behavior, but not the exact mechanism.",
            },
        ]
    }


def _final_rank():
    return {
        "ranking": [
            {
                "idea_id": "a",
                "title": "A",
                "reasoning_score": 0.45,
                "final_score": 0.59,
                "evidence_status": "SUFFICIENT_RELEVANT_EVIDENCE",
                "evidence_signal": 1.0,
                "evidence_count": 1,
                "relevant_evidence_count": 1,
                "conflicting_evidence": False,
            },
            {
                "idea_id": "b",
                "title": "B",
                "reasoning_score": 0.46,
                "final_score": 0.46,
                "evidence_status": "INSUFFICIENT_EVIDENCE",
                "evidence_signal": 0.0,
                "evidence_count": 1,
                "relevant_evidence_count": 0,
                "conflicting_evidence": False,
            },
            {
                "idea_id": "c",
                "title": "C",
                "reasoning_score": 0.44,
                "final_score": 0.40,
                "evidence_status": "SUFFICIENT_RELEVANT_EVIDENCE",
                "evidence_signal": -0.6,
                "evidence_count": 1,
                "relevant_evidence_count": 1,
                "conflicting_evidence": False,
            },
        ]
    }


def test_one_run_extracts_reusable_shadow_patterns_without_experiment():
    memory = learn_from_run(_reasoning(), _evidence(), _final_rank(), run_id="run-1")

    assert memory["status"] == "MIND_FORGE_V2_FAST_CROSS_RUN_MEMORY_COMPLETE"
    assert memory["source"] == "RUN_EVIDENCE"
    assert memory["auto_apply_to_production"] is False
    assert memory["run_count"] == 1
    assert {row["pattern_code"] for row in memory["patterns"]} >= {
        "DIRECT_EVIDENCE_CONFIRMED_CLAIM",
        "GENERIC_EVIDENCE_REJECTED",
        "ADJACENT_NEGATIVE_SIGNAL",
    }
    assert all(row["truth_status"] == "EVIDENCE_DERIVED" for row in memory["patterns"])
    assert all(row["mode"] == "SHADOW_HINT" for row in memory["next_cycle_search_adjustments"])
    assert all(row["may_auto_reject_ideas"] is False for row in memory["next_cycle_search_adjustments"])


def test_run_two_consumes_run_one_patterns_without_changing_candidates_or_budget():
    baseline = build_top3_research_plan(_reasoning())
    memory = learn_from_run(_reasoning(), _evidence(), _final_rank(), run_id="run-1")
    adaptive = build_top3_research_plan(_reasoning(), memory)

    assert [r["idea_id"] for r in adaptive["requests"]] == [r["idea_id"] for r in baseline["requests"]]
    assert adaptive["request_count"] == baseline["request_count"] == 3
    assert adaptive["max_total_search_operations"] == baseline["max_total_search_operations"] == 3
    assert adaptive["adaptive_memory_mode"] == "SHADOW_ONLY"
    assert adaptive["adaptive_hint_count"] >= 2
    assert adaptive["may_auto_reject_ideas_from_memory"] is False
    questions = " ".join(
        hint["search_question"]
        for request in adaptive["requests"]
        for hint in request["shadow_search_hints"]
    ).lower()
    assert "direct" in questions
    assert "generic" in questions or "exact claim" in questions


def test_repeated_independent_pattern_accumulates_but_stays_shadow_only():
    first = learn_from_run(_reasoning(), _evidence(), _final_rank(), run_id="run-1")
    second = learn_from_run(_reasoning(), _evidence(), _final_rank(), run_id="run-2", prior_memory=first)

    direct = next(row for row in second["patterns"] if row["pattern_code"] == "DIRECT_EVIDENCE_CONFIRMED_CLAIM")
    generic = next(row for row in second["patterns"] if row["pattern_code"] == "GENERIC_EVIDENCE_REJECTED")
    assert direct["observation_count"] == 2
    assert generic["observation_count"] == 2
    assert second["run_count"] == 2
    assert second["pattern_activation_state"] == "ELIGIBLE_FOR_HUMAN_REVIEW"
    assert second["auto_apply_to_production"] is False


def test_duplicate_run_id_is_rejected():
    first = learn_from_run(_reasoning(), _evidence(), _final_rank(), run_id="run-1")
    with pytest.raises(ValueError, match="duplicate run"):
        learn_from_run(_reasoning(), _evidence(), _final_rank(), run_id="run-1", prior_memory=first)
