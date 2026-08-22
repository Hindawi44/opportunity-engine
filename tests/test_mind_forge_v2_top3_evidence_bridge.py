from scripts.mind_forge_v2_top3_evidence_bridge import run_top3_evidence_bridge


def _reasoning():
    return {
        "selected_idea_ids": ["a", "b", "c"],
        "assessments": [
            {"idea_id": "a", "title": "A", "composite_score": 0.72},
            {"idea_id": "b", "title": "B", "composite_score": 0.69},
            {"idea_id": "c", "title": "C", "composite_score": 0.66},
        ],
    }


def _plan():
    return {
        "max_total_search_operations": 3,
        "max_operations_per_request": 1,
        "requests": [
            {"idea_id": "a", "max_search_operations": 1},
            {"idea_id": "b", "max_search_operations": 1},
            {"idea_id": "c", "max_search_operations": 1},
        ],
    }


def test_bridge_enforces_three_searches_and_reranks():
    def fake(request):
        idea_id = request["idea_id"]
        stance = "CONTRADICTS" if idea_id == "a" else "SUPPORTS"
        return ([{
            "stance": stance,
            "confidence": 0.95,
            "source_type": "official",
            "source_ref": f"https://example.test/{idea_id}",
            "observation_text": f"Evidence for {idea_id}",
        }], 1)

    result = run_top3_evidence_bridge(_reasoning(), _plan(), fake)
    assert result["search_operations"] == 3
    assert result["observation_count"] == 3
    assert result["final_rank"]["selected_idea_ids"][0] == "b"


def test_bridge_rejects_executor_using_more_than_one_search():
    def bad(_request):
        return ([], 2)

    try:
        run_top3_evidence_bridge(_reasoning(), _plan(), bad)
    except RuntimeError as exc:
        assert "exactly one search operation" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
