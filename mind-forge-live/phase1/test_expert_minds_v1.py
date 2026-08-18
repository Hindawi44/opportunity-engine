from __future__ import annotations

from mind_forge.contracts_v1 import RunContract, TopicInput
from mind_forge.creative_engine_v1 import generate_ideas
from mind_forge.expert_minds_v1 import evaluate_with_expert_minds
from mind_forge.question_generator_v1 import generate_questions


def _benchmark():
    topic = TopicInput(topic="تصليح الملابس")
    questions = generate_questions(topic)
    creative = generate_ideas(topic, questions)
    experts = evaluate_with_expert_minds(creative)
    return topic, questions, creative, experts


def test_exactly_ten_unique_bounded_minds() -> None:
    _, _, _, experts = _benchmark()

    assert len(experts) == 10
    assert len({output.mind_id for output in experts}) == 10
    assert len({output.lens for output in experts}) == 10
    assert all(output.independent_reasoning for output in experts)


def test_every_mind_assesses_the_same_full_candidate_universe() -> None:
    _, _, creative, experts = _benchmark()
    universe = {idea.idea_id for idea in creative.ideas}

    assert len(universe) == 14
    for output in experts:
        assert set(output.assessed_idea_ids) == universe
        assert set(output.support_scores) == universe
        assert output.strongest_idea_id in universe


def test_minds_do_not_collapse_into_duplicate_opinions() -> None:
    _, _, _, experts = _benchmark()

    strongest = {output.strongest_idea_id for output in experts}
    score_profiles = {
        tuple(sorted(output.support_scores.items()))
        for output in experts
    }

    assert len(strongest) >= 8
    assert len(score_profiles) == 10


def test_each_mind_exposes_assumptions_objections_and_evidence_that_changes_view() -> None:
    _, _, _, experts = _benchmark()

    for output in experts:
        assert output.assumptions
        assert output.objections
        assert output.evidence_that_changes_view
        assert all(0.0 <= score <= 1.0 for score in output.support_scores.values())


def test_seed_to_questions_to_ideas_to_ten_minds_is_valid_run_contract() -> None:
    topic, questions, creative, experts = _benchmark()

    run = RunContract(
        run_id="benchmark-tailoring-expert-minds-v1",
        topic=topic,
        questions=questions,
        ideas=creative.ideas,
        expert_outputs=experts,
    )

    assert run.topic.topic == "تصليح الملابس"
    assert len(run.ideas) == 14
    assert len(run.expert_outputs) == 10


def test_literal_seed_requires_no_user_answer_before_expert_review() -> None:
    topic = TopicInput(topic="تصليح الملابس")
    creative = generate_ideas(topic)
    experts = evaluate_with_expert_minds(creative)

    assert creative.user_answer_required is False
    assert len(experts) == 10
    assert all(len(output.assessed_idea_ids) == 14 for output in experts)
