from __future__ import annotations

from mind_forge.contracts_v1 import CritiqueDisposition, TopicInput
from mind_forge.creative_engine_v1 import generate_ideas
from mind_forge.expert_minds_v1 import evaluate_with_expert_minds
from mind_forge.logic_engine_v1 import evaluate_logic
from mind_forge.critique_engine_v1 import critique_survivors


def _pipeline():
    topic = TopicInput(topic="تصليح الملابس")
    creative = generate_ideas(topic)
    experts = evaluate_with_expert_minds(creative)
    logic = evaluate_logic(topic, creative, experts)
    critique = critique_survivors(creative, logic)
    return topic, creative, experts, logic, critique


def test_critique_covers_only_logic_survivors() -> None:
    _, _, _, logic, critique = _pipeline()

    assert critique.critiqued_idea_ids == logic.survivor_idea_ids
    assert len(critique.critiques) == len(logic.survivor_idea_ids) == 6
    assert set(critique.critiqued_idea_ids).isdisjoint(logic.held_idea_ids)
    assert set(critique.critiqued_idea_ids).isdisjoint(logic.rejected_idea_ids)


def test_every_survivor_gets_failure_mode_falsification_and_low_cost_test() -> None:
    _, _, _, _, critique = _pipeline()

    for item in critique.critiques:
        assert item.failure_modes
        assert item.falsification_test
        assert item.low_cost_test
        assert item.rationale
        assert 0.0 <= item.severity <= 1.0


def test_devils_advocate_separates_survive_rework_and_evidence_needs() -> None:
    _, _, _, _, critique = _pipeline()

    assert len(critique.survived_idea_ids) == 3
    assert len(critique.rework_idea_ids) == 2
    assert len(critique.needs_evidence_idea_ids) == 1
    assert critique.rejected_idea_ids == []
    assert critique.devils_advocate_applied is True


def test_critique_partition_matches_contract_dispositions() -> None:
    _, _, _, _, critique = _pipeline()
    by_id = {item.idea_id: item for item in critique.critiques}

    for idea_id in critique.survived_idea_ids:
        assert by_id[idea_id].disposition is CritiqueDisposition.SURVIVES
    for idea_id in critique.rework_idea_ids:
        assert by_id[idea_id].disposition is CritiqueDisposition.REWORK
    for idea_id in critique.needs_evidence_idea_ids:
        assert by_id[idea_id].disposition is CritiqueDisposition.NEEDS_EVIDENCE
    for idea_id in critique.rejected_idea_ids:
        assert by_id[idea_id].disposition is CritiqueDisposition.REJECT


def test_critique_preserves_hidden_assumptions_instead_of_promoting_them_to_facts() -> None:
    _, creative, _, _, critique = _pipeline()
    ideas_by_id = {idea.idea_id: idea for idea in creative.ideas}

    for item in critique.critiques:
        assert item.hidden_assumptions == ideas_by_id[item.idea_id].assumptions
        assert any("pre-evidence" in line for line in item.rationale)
