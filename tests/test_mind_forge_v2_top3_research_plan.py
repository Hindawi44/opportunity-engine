from copy import deepcopy

import pytest

from scripts.mind_forge_v2_top3_research_plan import build_top3_research_plan


def _reasoning():
    return {
        "selected_idea_ids": ["a", "b", "c"],
        "assessments": [
            {"idea_id": "a", "title": "A", "mechanism_family": "x", "critique": {"key_assumption": "A demand exists", "key_risk": "A risk"}},
            {"idea_id": "b", "title": "B", "mechanism_family": "y", "critique": {"key_assumption": "B can be delivered", "key_risk": "B risk"}},
            {"idea_id": "c", "title": "C", "mechanism_family": "z", "critique": {"key_assumption": "C has a buyer", "key_risk": "C risk"}},
        ],
    }


def _memory():
    return {
        "auto_apply_to_production": False,
        "next_cycle_search_adjustments": [
            {
                "action": "TEST_WILLINGNESS_BEFORE_IDEA_EXPANSION",
                "search_question": "Do users take costly action to solve this pain?",
                "required_evidence": "Prefer payment, pilots, referrals, or switching behavior.",
                "origin_memory_id": "v2-observed-exp-1",
                "mode": "SHADOW_HINT",
                "may_change_search_priority": True,
                "may_auto_reject_ideas": False,
            }
        ],
    }


def test_exactly_one_request_per_top3_idea():
    result = build_top3_research_plan(_reasoning())
    assert result["request_count"] == 3
    assert result["max_total_search_operations"] == 3
    assert result["max_operations_per_request"] == 1
    assert [r["idea_id"] for r in result["requests"]] == ["a", "b", "c"]
    assert all(r["max_search_operations"] == 1 for r in result["requests"])


def test_uses_key_assumption_as_single_material_claim():
    result = build_top3_research_plan(_reasoning())
    assert [r["claim_text"] for r in result["requests"]] == ["A demand exists", "B can be delivered", "C has a buyer"]


def test_mechanism_family_does_not_change_plan():
    original = _reasoning()
    renamed = deepcopy(original)
    for i, row in enumerate(renamed["assessments"]):
        row["mechanism_family"] = f"random-{i}"
    assert build_top3_research_plan(original) == build_top3_research_plan(renamed)
    assert build_top3_research_plan(original)["uses_mechanism_family_for_routing"] is False


def test_shadow_memory_changes_context_not_candidates_or_budget():
    base = build_top3_research_plan(_reasoning())
    learned = build_top3_research_plan(_reasoning(), _memory())
    assert [r["idea_id"] for r in learned["requests"]] == [r["idea_id"] for r in base["requests"]]
    assert learned["request_count"] == base["request_count"] == 3
    assert learned["max_total_search_operations"] == base["max_total_search_operations"] == 3
    assert learned["adaptive_memory_mode"] == "SHADOW_ONLY"
    assert learned["adaptive_hint_count"] == 1
    assert learned["may_auto_reject_ideas_from_memory"] is False
    assert all(r["shadow_search_hints"][0]["origin_memory_id"] == "v2-observed-exp-1" for r in learned["requests"])


def test_shadow_memory_cannot_enable_auto_rejection_or_production_rules():
    bad = _memory()
    bad["next_cycle_search_adjustments"][0]["may_auto_reject_ideas"] = True
    with pytest.raises(ValueError, match="may not auto-reject"):
        build_top3_research_plan(_reasoning(), bad)

    bad2 = _memory()
    bad2["auto_apply_to_production"] = True
    with pytest.raises(ValueError, match="may not auto-apply"):
        build_top3_research_plan(_reasoning(), bad2)


def test_rejects_more_or_fewer_than_three_candidates():
    data = _reasoning()
    data["selected_idea_ids"] = ["a", "b"]
    with pytest.raises(ValueError, match="exactly 3"):
        build_top3_research_plan(data)
