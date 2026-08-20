from __future__ import annotations

from mind_forge.contracts_v1 import (
    Constraint,
    ConstraintSource,
    ExpertMindOutput,
    TopicInput,
)
from mind_forge.creative_engine_v1 import CreativeEngineResult, generate_ideas
from mind_forge.expert_minds_v1 import evaluate_with_expert_minds
from mind_forge.logic_engine_v1 import LogicDisposition, evaluate_logic


def _benchmark():
    topic = TopicInput(topic="تصليح الملابس")
    creative = generate_ideas(topic)
    experts = evaluate_with_expert_minds(creative)
    return topic, creative, experts


def test_topic_only_logic_reduces_14_ideas_to_smaller_survivor_set() -> None:
    topic, creative, experts = _benchmark()

    result = evaluate_logic(topic, creative, experts)

    assert len(result.assessed_idea_ids) == 14
    assert len(result.assessments) == 14
    assert 1 <= len(result.survivor_idea_ids) < 14
    assert len(result.survivor_idea_ids) == 6
    assert len(result.held_idea_ids) == 8
    assert result.rejected_idea_ids == []
    assert result.uses_expert_popularity_for_gating is False


def test_logic_partitions_are_disjoint_and_exhaustive() -> None:
    topic, creative, experts = _benchmark()

    result = evaluate_logic(topic, creative, experts)

    survivors = set(result.survivor_idea_ids)
    held = set(result.held_idea_ids)
    rejected = set(result.rejected_idea_ids)
    assessed = set(result.assessed_idea_ids)

    assert not (survivors & held)
    assert not (survivors & rejected)
    assert not (held & rejected)
    assert survivors | held | rejected == assessed


def test_expert_popularity_cannot_override_explicit_constraint_failure() -> None:
    topic = TopicInput(
        topic="تصليح الملابس",
        constraints=[
            Constraint(
                name="forbidden_capabilities",
                value=["capacity reservation"],
                source=ConstraintSource.USER,
                confidence=1.0,
            )
        ],
    )
    creative = generate_ideas(topic)
    target_id = next(
        idea_id
        for idea_id, family in creative.mechanism_family_by_idea_id.items()
        if family == "premium_speed"
    )

    experts = []
    universe = [idea.idea_id for idea in creative.ideas]
    for index in range(10):
        scores = {idea_id: (1.0 if idea_id == target_id else 0.0) for idea_id in universe}
        experts.append(
            ExpertMindOutput(
                mind_id=f"synthetic-{index}",
                lens=f"Synthetic lens {index}",
                assessed_idea_ids=universe,
                strongest_idea_id=target_id,
                independent_reasoning=["Synthetic popularity stress test."],
                support_scores=scores,
            )
        )

    result = evaluate_logic(topic, creative, experts)
    assessment = next(item for item in result.assessments if item.idea_id == target_id)

    assert assessment.expert_support_mean == 1.0
    assert assessment.disposition is LogicDisposition.REJECT_CONSTRAINT
    assert target_id in result.rejected_idea_ids
    assert target_id not in result.survivor_idea_ids


def test_changing_expert_scores_does_not_change_logic_gate() -> None:
    topic, creative, experts = _benchmark()
    original = evaluate_logic(topic, creative, experts)

    inverted: list[ExpertMindOutput] = []
    for output in experts:
        scores = {idea_id: round(1.0 - score, 4) for idea_id, score in output.support_scores.items()}
        strongest_id = max(scores, key=lambda idea_id: (scores[idea_id], idea_id))
        inverted.append(
            ExpertMindOutput(
                mind_id=output.mind_id,
                lens=output.lens,
                assessed_idea_ids=list(output.assessed_idea_ids),
                strongest_idea_id=strongest_id,
                independent_reasoning=list(output.independent_reasoning),
                assumptions=list(output.assumptions),
                objections=list(output.objections),
                evidence_that_changes_view=list(output.evidence_that_changes_view),
                support_scores=scores,
            )
        )

    changed = evaluate_logic(topic, creative, inverted)

    assert changed.survivor_idea_ids == original.survivor_idea_ids
    assert changed.held_idea_ids == original.held_idea_ids
    assert changed.rejected_idea_ids == original.rejected_idea_ids


def test_structurally_incomplete_idea_is_rejected_before_popularity() -> None:
    topic, creative, experts = _benchmark()
    broken_idea = creative.ideas[0].model_copy(update={"core_mechanism": None})
    broken_creative = CreativeEngineResult(
        topic=creative.topic,
        ideas=[broken_idea, *creative.ideas[1:]],
        mechanism_family_by_idea_id=dict(creative.mechanism_family_by_idea_id),
        mechanism_diversity_ratio=creative.mechanism_diversity_ratio,
        source_question_ids=list(creative.source_question_ids),
        user_answer_required=False,
    )

    result = evaluate_logic(topic, broken_creative, experts)
    assessment = next(item for item in result.assessments if item.idea_id == broken_idea.idea_id)

    assert assessment.disposition is LogicDisposition.REJECT_STRUCTURAL
    assert "missing core mechanism" in assessment.structural_failures
    assert broken_idea.idea_id in result.rejected_idea_ids


def test_logic_keeps_assumptions_unresolved_instead_of_turning_them_into_facts() -> None:
    topic, creative, experts = _benchmark()

    result = evaluate_logic(topic, creative, experts)

    by_id = {item.idea_id: item for item in result.assessments}
    for idea in creative.ideas:
        assert by_id[idea.idea_id].unresolved_assumptions == idea.assumptions
        assert by_id[idea.idea_id].rationale
