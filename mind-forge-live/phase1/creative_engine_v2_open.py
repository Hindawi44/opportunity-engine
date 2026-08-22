from __future__ import annotations

import re
from hashlib import sha256
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts_v1 import Idea, Question, TopicInput
from .creative_engine_v1 import CreativeEngineResult, generate_ideas as generate_v1_ideas


class OpenIdeaDraft(BaseModel):
    """One model-generated idea with no pre-assigned mechanism family."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    mechanism_family: str = Field(min_length=1)
    core_mechanism: str = Field(min_length=1)
    customer_value: str = Field(min_length=1)
    business_value: str = Field(min_length=1)
    required_capabilities: list[str] = Field(min_length=1, max_length=6)
    assumptions: list[str] = Field(min_length=1, max_length=5)
    risks: list[str] = Field(min_length=1, max_length=5)
    novelty_reason: str = Field(min_length=1)
    source_question_ids: list[str] = Field(min_length=1, max_length=6)


class OpenCreativePayload(BaseModel):
    """Open creative output. Ideas are created from the seed/questions, not rewritten frames."""

    model_config = ConfigDict(extra="forbid")

    ideas: list[OpenIdeaDraft] = Field(min_length=14, max_length=14)

    @model_validator(mode="after")
    def require_real_diversity(self) -> "OpenCreativePayload":
        titles = [item.title.strip().casefold() for item in self.ideas]
        if len(set(titles)) != len(titles):
            raise ValueError("open creative output contains duplicate titles")
        families = [item.mechanism_family.strip().casefold() for item in self.ideas]
        if len(set(families)) < 8:
            raise ValueError("open creative output must span at least eight mechanism families")
        return self


def _stable_open_id(topic: str, title: str, index: int) -> str:
    digest = sha256(
        f"v2-open\x1f{topic.strip().casefold()}\x1f{index}\x1f{title.strip().casefold()}".encode("utf-8")
    ).hexdigest()[:16]
    return f"idea-open-{digest}"


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[\w-]+", text.casefold(), flags=re.UNICODE)
        if len(token) >= 3
    }


def _draft_text(draft: OpenIdeaDraft) -> str:
    parts = [
        draft.title,
        draft.core_mechanism,
        draft.customer_value,
        draft.business_value,
        draft.novelty_reason,
        *draft.required_capabilities,
        *draft.assumptions,
        *draft.risks,
    ]
    return " ".join(parts)


def _canonical_source_question_ids(
    draft: OpenIdeaDraft,
    internal_questions: list[Question],
) -> list[str]:
    """Return only real internal-question IDs, deterministically repairing hallucinated IDs.

    Valid model-supplied IDs are preserved in order. If the model supplied only unknown
    IDs, the idea is linked to the closest real internal question by lexical overlap.
    This repair is local and deterministic: it never makes another model request and the
    final strict subset validation in ``apply_open_payload`` remains authoritative.
    """

    if not internal_questions:
        raise ValueError("Creative V2 requires at least one internal question")

    allowed_ids = {item.question_id for item in internal_questions}
    valid: list[str] = []
    seen: set[str] = set()
    for question_id in draft.source_question_ids:
        if question_id in allowed_ids and question_id not in seen:
            valid.append(question_id)
            seen.add(question_id)
    if valid:
        return valid

    idea_tokens = _tokens(_draft_text(draft))
    best_question = internal_questions[0]
    best_score = -1
    for question in internal_questions:
        score = len(idea_tokens & _tokens(f"{question.text} {question.purpose}"))
        if score > best_score:
            best_question = question
            best_score = score

    return [best_question.question_id]


def open_creative_prompt(topic: TopicInput, questions: Iterable[Question]) -> str:
    question_rows = [
        {
            "question_id": item.question_id,
            "text": item.text,
            "purpose": item.purpose,
            "kind": item.kind.value,
        }
        for item in questions
        if item.kind.value == "INTERNAL"
    ]
    allowed_ids = [row["question_id"] for row in question_rows]
    return (
        "You are MIND FORGE Creative Engine V2. Generate exactly 14 genuinely different "
        "ideas from the topic and its internal questions. You are NOT rewriting a supplied "
        "idea list and you are NOT constrained to predefined mechanism families. Discover "
        "the opportunity space from the meaning of the seed itself. Create a concise "
        "mechanism_family label for each idea after you invent the mechanism. Across the 14 "
        "ideas use at least eight distinct mechanism families. Prefer concrete mechanisms "
        "that are specific to the topic over generic business wrappers such as membership, "
        "premium speed, mobile access, or partnerships unless the topic itself strongly "
        "supports them. Do not invent market facts, prices, laws, competitors, or demand. "
        "Put uncertain premises in assumptions. Every idea must cite one or more supplied "
        "internal question IDs in source_question_ids. Use ONLY exact IDs from ALLOWED_QUESTION_IDS; "
        "never invent, abbreviate, rewrite, or infer a question ID. Return concise structured fields in "
        "English even when the seed is Arabic.\n\n"
        f"TOPIC:\n{topic.model_dump_json()}\n\n"
        f"ALLOWED_QUESTION_IDS:\n{allowed_ids!r}\n\n"
        f"INTERNAL QUESTIONS:\n{question_rows!r}"
    )


def apply_open_payload(
    topic: TopicInput,
    questions: Iterable[Question],
    payload: OpenCreativePayload,
) -> CreativeEngineResult:
    question_list = list(questions)
    internal_questions = [
        item
        for item in question_list
        if item.kind.value == "INTERNAL"
    ]
    question_ids = {item.question_id for item in internal_questions}
    if not question_ids:
        raise ValueError("Creative V2 requires at least one internal question")

    ideas: list[Idea] = []
    family_by_id: dict[str, str] = {}
    used_ids: set[str] = set()

    for index, draft in enumerate(payload.ideas):
        canonical_question_ids = _canonical_source_question_ids(draft, internal_questions)
        if not canonical_question_ids or not set(canonical_question_ids).issubset(question_ids):
            raise ValueError("open creative idea cites an unknown internal question")

        idea_id = _stable_open_id(topic.topic, draft.title, index)
        if idea_id in used_ids:
            raise ValueError("open creative stable IDs collided")
        used_ids.add(idea_id)
        family = draft.mechanism_family.strip()
        family_by_id[idea_id] = family
        ideas.append(
            Idea(
                idea_id=idea_id,
                title=draft.title,
                core_mechanism=draft.core_mechanism,
                customer_value=draft.customer_value,
                business_value=draft.business_value,
                required_capabilities=draft.required_capabilities,
                assumptions=draft.assumptions,
                risks=draft.risks,
                novelty_reason=draft.novelty_reason,
                source_question_ids=canonical_question_ids,
            )
        )

    unique_families = len({value.casefold() for value in family_by_id.values()})
    return CreativeEngineResult(
        topic=topic.topic,
        ideas=ideas,
        mechanism_family_by_idea_id=family_by_id,
        mechanism_diversity_ratio=unique_families / len(ideas),
        source_question_ids=sorted({qid for idea in ideas for qid in idea.source_question_ids}),
        user_answer_required=False,
    )


def v1_benchmark(topic: TopicInput, questions: Iterable[Question]) -> CreativeEngineResult:
    """Keep deterministic V1 available only as benchmark/fallback, never as V2 idea frames."""
    return generate_v1_ideas(topic, questions)
