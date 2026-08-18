from __future__ import annotations

from collections.abc import Iterable
from enum import Enum

from .contracts_v1 import Question, QuestionKind, TopicInput


class QuestionStage(str, Enum):
    IDEATION = "IDEATION"
    DECISION = "DECISION"
    EXPERIMENT = "EXPERIMENT"


_INTERNAL_SPECS = (
    (
        "value_leak",
        "Where does value, time, money, or customer trust leak in {topic}?",
        "Identify hidden loss before proposing solutions.",
        0.90,
    ),
    (
        "underserved_segments",
        "Which customer segments or use cases are underserved in {topic}?",
        "Find unmet demand and asymmetric opportunities.",
        0.82,
    ),
    (
        "bottlenecks",
        "Which bottlenecks most constrain quality, speed, capacity, or growth in {topic}?",
        "Expose constraints that dominate system performance.",
        0.90,
    ),
    (
        "standardization",
        "Which parts of {topic} can be standardized without damaging quality or trust?",
        "Find repeatable operating leverage.",
        0.78,
    ),
    (
        "adjacent_value",
        "Which adjacent services, products, partnerships, or workflows could create disproportionate value around {topic}?",
        "Expand the idea space beyond incremental optimization.",
        0.74,
    ),
    (
        "pricing",
        "Where could pricing, packaging, guarantees, or service tiers change the economics of {topic}?",
        "Explore business-model and monetization leverage.",
        0.76,
    ),
    (
        "distribution",
        "Where does demand originate, how does it flow, and where could distribution be captured in {topic}?",
        "Expose acquisition and channel advantages.",
        0.80,
    ),
    (
        "replication",
        "What would have to become repeatable for {topic} to work with less dependence on one person or one location?",
        "Test scalability and owner-independence early.",
        0.76,
    ),
)


_USER_SPECS = (
    (
        "strategic_goal",
        "What outcome matters most: local profitability, growth, owner-independence, or another goal?",
        "Resolve the objective function only when ranking materially depends on it.",
        "strategic_goal",
        0.95,
        0.18,
        0.95,
    ),
    (
        "capital_limit",
        "What is the maximum capital you are willing to put at risk in the next test?",
        "Bound irreversible downside before choosing a capital-dependent action.",
        "capital_limit",
        0.90,
        0.20,
        0.90,
    ),
    (
        "risk_tolerance",
        "What level of downside or failure risk is acceptable for the next test?",
        "Use a personal risk constraint only when it changes the decision.",
        "risk_tolerance",
        0.86,
        0.22,
        0.88,
    ),
    (
        "owner_time",
        "How much owner time may the next test consume?",
        "Prevent a seemingly attractive idea from violating the user's time constraint.",
        "owner_time",
        0.82,
        0.20,
        0.84,
    ),
)


def _known_constraint_names(topic: TopicInput) -> set[str]:
    return {constraint.name.strip().lower() for constraint in topic.constraints}


def _goal_is_known(topic: TopicInput) -> bool:
    return bool([goal for goal in topic.goals if goal.strip()])


def generate_questions(topic: TopicInput) -> list[Question]:
    """Generate a broad question space from a raw topic without blocking ideation.

    Internal questions are immediately usable by the system. User-facing questions
    are candidates only; adaptive selection decides whether any should interrupt the
    user at the current stage.
    """

    questions: list[Question] = []
    for key, text, purpose, materiality in _INTERNAL_SPECS:
        questions.append(
            Question(
                question_id=f"q-internal-{key}",
                text=text.format(topic=topic.topic),
                kind=QuestionKind.INTERNAL,
                purpose=purpose,
                materiality=materiality,
                blocking=False,
            )
        )

    known = _known_constraint_names(topic)
    for key, text, purpose, variable, eig, interruption, materiality in _USER_SPECS:
        if variable == "strategic_goal" and _goal_is_known(topic):
            continue
        if variable in known:
            continue
        questions.append(
            Question(
                question_id=f"q-user-{key}",
                text=text,
                kind=QuestionKind.USER,
                purpose=purpose,
                decision_variable=variable,
                expected_information_gain=eig,
                interruption_cost=interruption,
                materiality=materiality,
                blocking=False,
            )
        )

    return questions


def select_user_questions(
    questions: Iterable[Question],
    *,
    stage: QuestionStage,
    decision_variables: Iterable[str] = (),
    max_questions: int = 1,
) -> list[Question]:
    """Return only high-value user questions needed by the current decision.

    IDEATION never blocks on user input. Later stages may surface at most a small
    number of questions and only when their decision variable is explicitly active.
    """

    if max_questions < 0:
        raise ValueError("max_questions must be >= 0")
    if stage is QuestionStage.IDEATION or max_questions == 0:
        return []

    active_variables = {value.strip().lower() for value in decision_variables if value.strip()}
    if not active_variables:
        return []

    eligible = [
        question
        for question in questions
        if question.kind is QuestionKind.USER
        and question.decision_variable is not None
        and question.decision_variable.lower() in active_variables
        and question.should_ask_user
    ]
    eligible.sort(
        key=lambda question: (
            question.expected_information_gain - question.interruption_cost,
            question.materiality,
            question.expected_information_gain,
        ),
        reverse=True,
    )

    return [
        question.model_copy(update={"blocking": True})
        for question in eligible[:max_questions]
    ]


def build_adaptive_question_set(
    topic: TopicInput,
    *,
    stage: QuestionStage = QuestionStage.IDEATION,
    decision_variables: Iterable[str] = (),
    max_user_questions: int = 1,
) -> tuple[list[Question], list[Question]]:
    """Generate all questions and separately return the questions worth asking now."""

    generated = generate_questions(topic)
    ask_now = select_user_questions(
        generated,
        stage=stage,
        decision_variables=decision_variables,
        max_questions=max_user_questions,
    )
    return generated, ask_now
