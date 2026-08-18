from __future__ import annotations

import pytest
from pydantic import ValidationError

from mind_forge.contracts_v1 import Idea, QuestionKind, RunContract, TopicInput
from mind_forge.creative_engine_v1 import CreativeEngineResult, generate_ideas
from mind_forge.question_generator_v1 import generate_questions


def _benchmark() -> tuple[TopicInput, list]:
    topic = TopicInput(topic="تصليح الملابس")
    questions = generate_questions(topic)
    return topic, questions


def test_topic_only_generates_12_to_20_canonical_ideas() -> None:
    topic, questions = _benchmark()
    result = generate_ideas(topic, questions)
    assert 12 <= len(result.ideas) <= 20
    assert all(isinstance(idea, Idea) for idea in result.ideas)
    assert len({idea.idea_id for idea in result.ideas}) == len(result.ideas)
    assert len({idea.title for idea in result.ideas}) == len(result.ideas)
    assert all(idea.core_mechanism for idea in result.ideas)
    assert all(idea.business_value for idea in result.ideas)
    assert all(idea.risks for idea in result.ideas)


def test_literal_seed_alone_invokes_internal_question_generation() -> None:
    topic = TopicInput(topic="تصليح الملابس")
    result = generate_ideas(topic)
    assert len(result.ideas) == 14
    assert result.user_answer_required is False
    assert result.source_question_ids
    assert result.mechanism_diversity_ratio == 1.0


def test_creative_engine_uses_internal_questions_without_user_answer() -> None:
    topic, questions = _benchmark()
    internal_ids = {q.question_id for q in questions if q.kind is QuestionKind.INTERNAL}
    result = generate_ideas(topic, questions)
    assert result.user_answer_required is False
    assert result.source_question_ids
    assert set(result.source_question_ids).issubset(internal_ids)
    assert all(idea.source_question_ids for idea in result.ideas)
    assert all(set(idea.source_question_ids).issubset(internal_ids) for idea in result.ideas)


def test_topic_questions_and_ideas_form_a_valid_run_contract() -> None:
    topic, questions = _benchmark()
    result = generate_ideas(topic, questions)
    run = RunContract(
        run_id="benchmark-tailoring-creative-v1",
        topic=topic,
        questions=questions,
        ideas=result.ideas,
    )
    assert run.topic.topic == "تصليح الملابس"
    assert len(run.questions) >= 12
    assert len(run.ideas) == 14


def test_mechanism_diversity_is_structural_not_title_only() -> None:
    topic, questions = _benchmark()
    result = generate_ideas(topic, questions)
    families = list(result.mechanism_family_by_idea_id.values())
    assert len(set(families)) >= 12
    assert result.mechanism_diversity_ratio >= 0.85
    required_families = {
        "bottleneck_redesign",
        "standardization",
        "premium_speed",
        "recurring_membership",
        "distribution_partnership",
        "b2b_embedding",
        "automation_intake",
        "circular_recovery",
        "replication_licensing",
    }
    assert required_families.issubset(set(families))


def test_each_idea_explains_why_it_is_not_a_duplicate() -> None:
    topic, questions = _benchmark()
    result = generate_ideas(topic, questions)
    assert all(idea.novelty_reason for idea in result.ideas)
    assert all(len(idea.novelty_reason or "") >= 20 for idea in result.ideas)


def test_generation_is_deterministic_for_same_topic_and_questions() -> None:
    topic, questions = _benchmark()
    first = generate_ideas(topic, questions)
    second = generate_ideas(topic, questions)
    assert [idea.model_dump(mode="json") for idea in first.ideas] == [
        idea.model_dump(mode="json") for idea in second.ideas
    ]
    assert first.mechanism_family_by_idea_id == second.mechanism_family_by_idea_id


def test_user_question_candidates_do_not_leak_into_idea_provenance() -> None:
    topic, questions = _benchmark()
    user_ids = {q.question_id for q in questions if q.kind is QuestionKind.USER}
    result = generate_ideas(topic, questions)
    used = {qid for idea in result.ideas for qid in idea.source_question_ids}
    assert used.isdisjoint(user_ids)


def test_result_rejects_family_map_that_does_not_cover_all_ideas() -> None:
    topic, questions = _benchmark()
    result = generate_ideas(topic, questions)
    bad_map = dict(result.mechanism_family_by_idea_id)
    bad_map.pop(next(iter(bad_map)))
    with pytest.raises(ValidationError):
        CreativeEngineResult(
            topic=result.topic,
            ideas=result.ideas,
            mechanism_family_by_idea_id=bad_map,
            mechanism_diversity_ratio=result.mechanism_diversity_ratio,
            source_question_ids=result.source_question_ids,
        )
