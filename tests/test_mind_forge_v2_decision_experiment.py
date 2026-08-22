from scripts.mind_forge_v2_decision_experiment import decide_and_design_experiment


def _reasoning():
    return {
        "assessments": [
            {
                "idea_id": "a",
                "title": "A",
                "mechanism_family": "ignored",
                "critique": {
                    "key_assumption": "Users have a material need",
                    "key_risk": "Interest may not convert",
                },
            }
        ]
    }


def _evidence():
    return {
        "observations": [
            {
                "idea_id": "a",
                "stance": "SUPPORTS",
                "confidence": 0.9,
                "source_ref": "https://example.test/a",
                "observation_text": "support",
            }
        ]
    }


def test_strong_supported_top_idea_goes_to_experiment():
    final_rank = {
        "ranking": [
            {
                "idea_id": "a",
                "title": "A",
                "final_score": 0.63,
                "evidence_signal": 0.85,
                "evidence_count": 1,
                "conflicting_evidence": False,
            }
        ]
    }
    result = decide_and_design_experiment(final_rank, _reasoning(), _evidence())
    assert result["decision"] == "EXPERIMENT"
    assert result["experiment"]["duration_days"] == 7
    assert result["experiment"]["max_cash_commitment_nok"] == 1000
    assert result["experiment"]["success_criteria"]["minimum_concrete_commitments"] == 2
    assert result["uses_mechanism_family_for_decision"] is False


def test_weak_or_negative_idea_is_rejected():
    final_rank = {
        "ranking": [
            {
                "idea_id": "a",
                "title": "A",
                "final_score": 0.42,
                "evidence_signal": -0.5,
                "evidence_count": 1,
                "conflicting_evidence": False,
            }
        ]
    }
    result = decide_and_design_experiment(final_rank, _reasoning(), _evidence())
    assert result["decision"] == "REJECT"
    assert result["experiment"] is None


def test_conflicting_evidence_holds_instead_of_experimenting():
    final_rank = {
        "ranking": [
            {
                "idea_id": "a",
                "title": "A",
                "final_score": 0.64,
                "evidence_signal": 0.3,
                "evidence_count": 1,
                "conflicting_evidence": True,
            }
        ]
    }
    result = decide_and_design_experiment(final_rank, _reasoning(), _evidence())
    assert result["decision"] == "HOLD"
    assert result["experiment"] is None


def test_family_label_cannot_change_decision():
    final_rank = {
        "ranking": [
            {
                "idea_id": "a",
                "title": "A",
                "final_score": 0.63,
                "evidence_signal": 0.8,
                "evidence_count": 1,
                "conflicting_evidence": False,
            }
        ]
    }
    first = _reasoning()
    second = _reasoning()
    second["assessments"][0]["mechanism_family"] = "completely-random-family"
    assert decide_and_design_experiment(final_rank, first, _evidence()) == decide_and_design_experiment(final_rank, second, _evidence())


def test_relevance_gate_insufficient_evidence_cannot_trigger_experiment():
    final_rank = {
        "evidence_relevance_gate": "ENFORCED",
        "ranking": [
            {
                "idea_id": "a",
                "title": "A",
                "final_score": 0.66,
                "evidence_signal": 0.8,
                "evidence_count": 1,
                "relevant_evidence_count": 0,
                "evidence_status": "INSUFFICIENT_EVIDENCE",
                "conflicting_evidence": False,
            }
        ],
    }
    result = decide_and_design_experiment(final_rank, _reasoning(), _evidence())

    assert result["decision"] == "HOLD"
    assert result["experiment"] is None
    assert result["evidence_status"] == "INSUFFICIENT_EVIDENCE"
    assert result["relevant_evidence_count"] == 0
