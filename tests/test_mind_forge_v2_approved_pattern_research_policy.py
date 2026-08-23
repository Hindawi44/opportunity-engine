import sys
import types


if "agents" not in sys.modules:
    agents_stub = types.ModuleType("agents")

    class _AgentsStub:
        pass

    agents_stub.Agent = _AgentsStub
    agents_stub.ModelSettings = _AgentsStub
    agents_stub.Runner = _AgentsStub
    agents_stub.WebSearchTool = _AgentsStub
    sys.modules["agents"] = agents_stub

from scripts.mind_forge_v2_live_evidence_runtime import _build_plan, _prompt
from scripts.mind_forge_v2_top3_research_plan import build_top3_research_plan


def _reasoning():
    return {
        "seed": "raw seed",
        "selected_idea_ids": ["a", "b", "c"],
        "assessments": [
            {"idea_id": "a", "title": "A", "critique": {"key_assumption": "Claim A"}},
            {"idea_id": "b", "title": "B", "critique": {"key_assumption": "Claim B"}},
            {"idea_id": "c", "title": "C", "critique": {"key_assumption": "Claim C"}},
        ],
    }


def _approved_memory():
    pattern_id = "v2-fast-generic-evidence-rejected"
    return {
        "status": "MIND_FORGE_V2_FAST_CROSS_RUN_MEMORY_COMPLETE",
        "source": "RUN_EVIDENCE",
        "auto_apply_to_production": False,
        "patterns": [
            {
                "pattern_id": pattern_id,
                "pattern_code": "GENERIC_EVIDENCE_REJECTED",
                "truth_status": "EVIDENCE_DERIVED",
                "source": "RUN_EVIDENCE",
                "observation_count": 5,
                "run_ids": ["r1", "r2", "r3", "r4", "r5"],
                "example_idea_ids": ["i1", "i2", "i3"],
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
        "pattern_applications": [
            {
                "application_id": "approval-001",
                "pattern_id": pattern_id,
                "pattern_code": "GENERIC_EVIDENCE_REJECTED",
                "status": "ACTIVE",
                "approved_by": "Hindawi44",
                "approved_at_independent_run_count": 5,
                "approved_at_example_diversity_count": 3,
                "human_approval_recorded": True,
                "may_auto_reject_ideas": False,
            }
        ],
    }


def test_approved_pattern_replaces_same_shadow_hint_without_changing_candidates_or_budget():
    baseline = build_top3_research_plan(_reasoning())
    adaptive = build_top3_research_plan(_reasoning(), _approved_memory())

    assert [r["idea_id"] for r in adaptive["requests"]] == [r["idea_id"] for r in baseline["requests"]]
    assert adaptive["request_count"] == baseline["request_count"] == 3
    assert adaptive["max_total_search_operations"] == baseline["max_total_search_operations"] == 3
    assert adaptive["adaptive_memory_mode"] == "APPROVED_POLICY"
    assert adaptive["approved_policy_count"] == 1
    assert adaptive["adaptive_hint_count"] == 0
    assert adaptive["may_auto_reject_ideas_from_memory"] is False
    assert all(len(row["approved_search_policies"]) == 1 for row in adaptive["requests"])
    assert all(row["shadow_search_hints"] == [] for row in adaptive["requests"])


def test_live_prompt_marks_human_approved_policy_as_search_guidance_not_evidence_or_decision():
    plan = _build_plan(_reasoning(), prior_memory=_approved_memory())
    prompt = _prompt(plan[0])

    assert "APPROVED CROSS-RUN POLICY" in prompt
    assert "human-approved" in prompt.lower()
    assert "cannot alter the candidate set" in prompt.lower()
    assert "cannot change the search budget" in prompt.lower()
    assert "not evidence" in prompt.lower()
    assert "REQUIRE_EXACT_CLAIM_RELEVANCE" in prompt
    assert "PRIOR CROSS-RUN LEARNING" not in prompt
