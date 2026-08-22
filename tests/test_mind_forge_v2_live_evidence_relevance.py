from scripts.mind_forge_v2_live_evidence_runtime import _build_plan, _prompt, _rerank


def _reasoning(base_score: float = 0.60):
    return {
        "seed": "تصليح الملابس",
        "selected_idea_ids": ["idea-1"],
        "assessments": [
            {
                "idea_id": "idea-1",
                "title": "Repair Queue Exchange",
                "composite_score": base_score,
                "critique": {
                    "key_assumption": "Independent garment repairers can share specialist work efficiently."
                },
            }
        ],
    }


def test_plan_and_prompt_carry_original_topic_for_domain_relevance():
    reasoning = _reasoning()
    reasoning["selected_idea_ids"] = ["idea-1", "idea-2", "idea-3"]
    reasoning["assessments"].extend(
        [
            {
                "idea_id": "idea-2",
                "title": "Failure Pattern Network",
                "composite_score": 0.58,
                "critique": {"key_assumption": "Garment failure patterns can improve repair decisions."},
            },
            {
                "idea_id": "idea-3",
                "title": "Transparent Repair Menu",
                "composite_score": 0.57,
                "critique": {"key_assumption": "Customers value standardized garment repair offers."},
            },
        ]
    )

    plan = _build_plan(reasoning)
    assert all(row["topic"] == "تصليح الملابس" for row in plan)
    prompt = _prompt(plan[0])
    assert "TOPIC: تصليح الملابس" in prompt
    assert "GENERIC" in prompt
    assert "OFF_DOMAIN" in prompt


def test_generic_supporting_source_cannot_boost_final_rank():
    base = 0.60
    result = _rerank(
        _reasoning(base),
        [
            {
                "idea_id": "idea-1",
                "stance": "SUPPORTS",
                "confidence": 0.90,
                "source_type": "official",
                "source_ref": "https://example.gov/right-to-repair-cars",
                "relevance": "GENERIC",
            }
        ],
    )
    row = result["ranking"][0]

    assert row["evidence_status"] == "INSUFFICIENT_EVIDENCE"
    assert row["relevant_evidence_count"] == 0
    assert row["evidence_score"] == 0.5
    assert row["final_score"] == base


def test_off_domain_supporting_source_cannot_boost_final_rank():
    base = 0.60
    result = _rerank(
        _reasoning(base),
        [
            {
                "idea_id": "idea-1",
                "stance": "SUPPORTS",
                "confidence": 0.90,
                "source_type": "official",
                "source_ref": "https://example.gov/automotive-repair-statistics",
                "relevance": "OFF_DOMAIN",
            }
        ],
    )
    row = result["ranking"][0]

    assert row["evidence_status"] == "INSUFFICIENT_EVIDENCE"
    assert row["relevant_evidence_count"] == 0
    assert row["final_score"] == base


def test_direct_domain_evidence_can_change_rank_with_bounded_strength():
    base = 0.60
    result = _rerank(
        _reasoning(base),
        [
            {
                "idea_id": "idea-1",
                "stance": "SUPPORTS",
                "confidence": 0.90,
                "source_type": "official",
                "source_ref": "https://example.gov/garment-repair-demand",
                "relevance": "DIRECT",
            }
        ],
    )
    row = result["ranking"][0]

    assert row["evidence_status"] == "SUFFICIENT_RELEVANT_EVIDENCE"
    assert row["relevant_evidence_count"] == 1
    assert 0.5 < row["evidence_score"] <= 1.0
    assert row["final_score"] > base


def test_missing_relevance_fails_closed_instead_of_boosting():
    base = 0.60
    result = _rerank(
        _reasoning(base),
        [
            {
                "idea_id": "idea-1",
                "stance": "SUPPORTS",
                "confidence": 0.90,
                "source_type": "official",
                "source_ref": "https://example.gov/unknown-domain",
            }
        ],
    )
    row = result["ranking"][0]

    assert row["evidence_status"] == "INSUFFICIENT_EVIDENCE"
    assert row["final_score"] == base
