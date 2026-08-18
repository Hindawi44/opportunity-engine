from __future__ import annotations

from mind_forge.contracts_v1 import Constraint, ConstraintSource, QuestionKind, TopicInput
from mind_forge.question_generator_v1 import (
    QuestionStage,
    build_adaptive_question_set,
    generate_questions,
    select_user_questions,
)


def test_topic_only_generates_internal_questions_without_interrupting_user() -> None:
    topic = TopicInput(topic="تصليح الملابس")

    generated, ask_now = build_adaptive_question_set(topic)

    internal = [q for q in generated if q.kind is QuestionKind.INTERNAL]
    user_candidates = [q for q in generated if q.kind is QuestionKind.USER]

    assert len(internal) >= 8
    assert len(user_candidates) >= 4
    assert ask_now == []
    assert all(not question.blocking for question in generated)
    assert all("تصليح الملابس" in question.text for question in internal)


def test_decision_stage_asks_only_one_high_value_active_variable() -> None:
    topic = TopicInput(topic="تصليح الملابس")
    generated = generate_questions(topic)

    ask_now = select_user_questions(
        generated,
        stage=QuestionStage.DECISION,
        decision_variables=["capital_limit", "risk_tolerance"],
        max_questions=1,
    )

    assert len(ask_now) == 1
    assert ask_now[0].decision_variable in {"capital_limit", "risk_tolerance"}
    assert ask_now[0].blocking is True
    assert ask_now[0].should_ask_user is True


def test_irrelevant_user_questions_are_not_asked() -> None:
    topic = TopicInput(topic="تصليح الملابس")
    generated = generate_questions(topic)

    ask_now = select_user_questions(
        generated,
        stage=QuestionStage.EXPERIMENT,
        decision_variables=["unknown_public_market_fact"],
    )

    assert ask_now == []


def test_known_user_constraints_are_not_asked_again() -> None:
    topic = TopicInput(
        topic="تصليح الملابس",
        goals=["زيادة الربح المحلي"],
        constraints=[
            Constraint(
                name="capital_limit",
                value=1000,
                source=ConstraintSource.USER,
                confidence=1.0,
            )
        ],
    )

    generated = generate_questions(topic)
    variables = {q.decision_variable for q in generated if q.kind is QuestionKind.USER}

    assert "strategic_goal" not in variables
    assert "capital_limit" not in variables
    assert "risk_tolerance" in variables


def test_zero_question_budget_never_interrupts() -> None:
    topic = TopicInput(topic="تصليح الملابس")
    generated = generate_questions(topic)

    ask_now = select_user_questions(
        generated,
        stage=QuestionStage.DECISION,
        decision_variables=["strategic_goal", "capital_limit"],
        max_questions=0,
    )

    assert ask_now == []
