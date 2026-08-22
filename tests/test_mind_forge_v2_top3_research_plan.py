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


def test_rejects_more_or_fewer_than_three_candidates():
    data = _reasoning()
    data["selected_idea_ids"] = ["a", "b"]
    with pytest.raises(ValueError, match="exactly 3"):
        build_top3_research_plan(data)
