from __future__ import annotations

import math
import os
from collections.abc import Callable, Iterable
from typing import Any

from agents import Agent, ModelSettings, Runner
from openai.types.shared import Reasoning
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts_v1 import ExpertMindOutput, Idea, Question, TopicInput
from .creative_engine_v1 import CreativeEngineResult, generate_ideas
from .expert_minds_v1 import _MIND_SPECS


# Current public GPT-5.6 list pricing, dollars per 1M text tokens.
# This table is intentionally small and fail-closed. Unknown models cannot run
# through the dollar budget gate until their pricing is explicitly reviewed.
_MODEL_PRICE_PER_MILLION: dict[str, tuple[float, float]] = {
    "gpt-5.6": (5.0, 30.0),
    "gpt-5.6-sol": (5.0, 30.0),
    "gpt-5.6-terra": (2.0, 12.0),
    "gpt-5.6-luna": (0.20, 1.20),
}


class LiveModelPolicy(BaseModel):
    """Explicit paid-model gate. No key value is ever stored in this object."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = False
    creative_model: str = "gpt-5.6-terra"
    expert_model: str = "gpt-5.6-luna"
    max_requests: int = Field(default=11, ge=1, le=11)
    max_input_tokens: int = Field(default=120_000, ge=1)
    max_output_tokens: int = Field(default=20_000, ge=1)
    max_estimated_cost_usd: float = Field(default=0.10, gt=0.0, le=0.25)
    creative_max_output_tokens: int = Field(default=3_500, ge=500, le=6_000)
    expert_max_output_tokens: int = Field(default=900, ge=300, le=1_500)
    creative_reasoning_effort: str = "medium"
    expert_reasoning_effort: str = "low"

    @model_validator(mode="after")
    def validate_known_models_and_budget_shape(self) -> "LiveModelPolicy":
        for model in (self.creative_model, self.expert_model):
            if model not in _MODEL_PRICE_PER_MILLION:
                raise ValueError(f"model {model!r} has no reviewed price entry")
        worst_output = self.creative_max_output_tokens + 10 * self.expert_max_output_tokens
        if worst_output > self.max_output_tokens:
            raise ValueError("per-call output ceilings exceed total output-token budget")
        return self


class LiveUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0


class LiveBudgetGate:
    """Pre-call and post-call guard for request, token, and estimated-dollar limits."""

    def __init__(self, policy: LiveModelPolicy) -> None:
        self.policy = policy
        self.usage = LiveUsage()
        self._reserved_requests = 0
        self._reserved_cost_usd = 0.0

    @staticmethod
    def _price(model: str, input_tokens: int, output_tokens: int) -> float:
        input_per_m, output_per_m = _MODEL_PRICE_PER_MILLION[model]
        return (input_tokens / 1_000_000.0) * input_per_m + (
            output_tokens / 1_000_000.0
        ) * output_per_m

    @staticmethod
    def _conservative_input_estimate(prompt: str) -> int:
        # UTF-8 bytes / 3 is deliberately conservative for mixed English/Arabic text.
        return max(1, math.ceil(len(prompt.encode("utf-8")) / 3.0))

    def reserve(self, *, model: str, prompt: str, max_output_tokens: int) -> None:
        next_requests = self._reserved_requests + 1
        if next_requests > self.policy.max_requests:
            raise RuntimeError("live model request budget exhausted")

        estimated_input = self._conservative_input_estimate(prompt)
        projected_input = self.usage.input_tokens + estimated_input
        projected_output = self.usage.output_tokens + max_output_tokens
        if projected_input > self.policy.max_input_tokens:
            raise RuntimeError("live model input-token budget would be exceeded")
        if projected_output > self.policy.max_output_tokens:
            raise RuntimeError("live model output-token budget would be exceeded")

        projected_cost = self.usage.estimated_cost_usd + self._price(
            model, estimated_input, max_output_tokens
        )
        if projected_cost > self.policy.max_estimated_cost_usd:
            raise RuntimeError("live model estimated-dollar budget would be exceeded")

        self._reserved_requests = next_requests
        self._reserved_cost_usd = projected_cost

    def record(self, *, model: str, result: Any) -> None:
        usage = result.context_wrapper.usage
        requests = int(getattr(usage, "requests", 1) or 1)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)

        self.usage.requests += requests
        self.usage.input_tokens += input_tokens
        self.usage.output_tokens += output_tokens
        self.usage.estimated_cost_usd = round(
            self.usage.estimated_cost_usd
            + self._price(model, input_tokens, output_tokens),
            8,
        )

        if self.usage.requests > self.policy.max_requests:
            raise RuntimeError("actual live model requests exceeded hard cap")
        if self.usage.input_tokens > self.policy.max_input_tokens:
            raise RuntimeError("actual live model input tokens exceeded hard cap")
        if self.usage.output_tokens > self.policy.max_output_tokens:
            raise RuntimeError("actual live model output tokens exceeded hard cap")
        if self.usage.estimated_cost_usd > self.policy.max_estimated_cost_usd:
            raise RuntimeError("actual estimated live model cost exceeded hard cap")


def assert_live_model_access(policy: LiveModelPolicy) -> None:
    if not policy.enabled:
        raise RuntimeError("live model policy is disabled")
    if os.getenv("MIND_FORGE_LIVE_ENABLED") != "1":
        raise RuntimeError("MIND_FORGE_LIVE_ENABLED=1 is required for paid model calls")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not available to the live runtime")


class LiveIdeaRewrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idea_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    core_mechanism: str = Field(min_length=1)
    customer_value: str = Field(min_length=1)
    business_value: str = Field(min_length=1)
    required_capabilities: list[str] = Field(min_length=1, max_length=6)
    assumptions: list[str] = Field(min_length=1, max_length=5)
    risks: list[str] = Field(min_length=1, max_length=5)
    novelty_reason: str = Field(min_length=1)


class LiveCreativePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ideas: list[LiveIdeaRewrite] = Field(min_length=14, max_length=14)

    @model_validator(mode="after")
    def require_unique_ids(self) -> "LiveCreativePayload":
        ids = [item.idea_id for item in self.ideas]
        if len(ids) != len(set(ids)):
            raise ValueError("live creative output contains duplicate idea IDs")
        return self


class LiveExpertDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strongest_idea_id: str = Field(min_length=1)
    independent_reasoning: list[str] = Field(min_length=2, max_length=8)
    assumptions: list[str] = Field(min_length=1, max_length=6)
    objections: list[str] = Field(min_length=1, max_length=6)
    evidence_that_changes_view: list[str] = Field(min_length=1, max_length=6)
    support_scores: dict[str, float]

    @model_validator(mode="after")
    def validate_scores(self) -> "LiveExpertDraft":
        for value in self.support_scores.values():
            if not 0.0 <= value <= 1.0:
                raise ValueError("expert support scores must be between 0 and 1")
        return self


RunnerCallable = Callable[..., Any]


def _coerce_output(value: Any, model_type: type[BaseModel]) -> BaseModel:
    if isinstance(value, model_type):
        return value
    return model_type.model_validate(value)


def _run_structured(
    agent: Agent,
    prompt: str,
    *,
    gate: LiveBudgetGate,
    model: str,
    max_output_tokens: int,
    runner: RunnerCallable,
) -> Any:
    gate.reserve(model=model, prompt=prompt, max_output_tokens=max_output_tokens)
    result = runner(agent, prompt, max_turns=1)
    gate.record(model=model, result=result)
    return result.final_output


def _creative_prompt(
    topic: TopicInput,
    questions: Iterable[Question],
    baseline: CreativeEngineResult,
) -> str:
    question_rows = [
        {"question_id": item.question_id, "text": item.text, "purpose": item.purpose}
        for item in questions
        if item.kind.value == "INTERNAL"
    ]
    idea_rows = []
    for idea in baseline.ideas:
        idea_rows.append(
            {
                "idea_id": idea.idea_id,
                "mechanism_family": baseline.mechanism_family_by_idea_id[idea.idea_id],
                "title": idea.title,
                "core_mechanism": idea.core_mechanism,
                "customer_value": idea.customer_value,
                "business_value": idea.business_value,
                "assumptions": idea.assumptions,
                "risks": idea.risks,
            }
        )
    return (
        "You are the live Creative Engine inside MIND FORGE. Improve the 14 bounded "
        "mechanism-family ideas for the supplied business topic. Preserve every idea_id "
        "exactly once and stay inside its stated mechanism family, but make the idea "
        "specific, commercially imaginative, and meaningfully different from the baseline. "
        "Do not invent market facts, customer counts, prices, laws, competitors, or demand. "
        "Any uncertain premise must remain in assumptions. Return internal structured fields "
        "in concise English even when the seed is Arabic.\n\n"
        f"TOPIC:\n{topic.model_dump_json()}\n\n"
        f"INTERNAL QUESTIONS:\n{question_rows!r}\n\n"
        f"BOUNDED IDEA FRAMES:\n{idea_rows!r}"
    )


def apply_live_creative_payload(
    baseline: CreativeEngineResult,
    payload: LiveCreativePayload,
) -> CreativeEngineResult:
    expected_ids = {item.idea_id for item in baseline.ideas}
    received_ids = {item.idea_id for item in payload.ideas}
    if received_ids != expected_ids:
        raise ValueError("live creative output must cover the exact baseline idea universe")

    baseline_by_id = {item.idea_id: item for item in baseline.ideas}
    rewritten_by_id = {item.idea_id: item for item in payload.ideas}
    ideas: list[Idea] = []
    for original in baseline.ideas:
        live = rewritten_by_id[original.idea_id]
        ideas.append(
            Idea(
                idea_id=original.idea_id,
                title=live.title,
                core_mechanism=live.core_mechanism,
                customer_value=live.customer_value,
                business_value=live.business_value,
                required_capabilities=live.required_capabilities,
                assumptions=live.assumptions,
                risks=live.risks,
                novelty_reason=live.novelty_reason,
                source_question_ids=baseline_by_id[original.idea_id].source_question_ids,
                status=original.status,
            )
        )

    return CreativeEngineResult(
        topic=baseline.topic,
        ideas=ideas,
        mechanism_family_by_idea_id=dict(baseline.mechanism_family_by_idea_id),
        mechanism_diversity_ratio=baseline.mechanism_diversity_ratio,
        source_question_ids=list(baseline.source_question_ids),
        user_answer_required=False,
    )


def generate_live_ideas(
    topic: TopicInput,
    questions: Iterable[Question],
    policy: LiveModelPolicy,
    gate: LiveBudgetGate,
    *,
    runner: RunnerCallable = Runner.run_sync,
) -> CreativeEngineResult:
    assert_live_model_access(policy)
    baseline = generate_ideas(topic, questions)
    prompt = _creative_prompt(topic, questions, baseline)
    agent = Agent(
        name="MIND FORGE Creative Engine",
        instructions=(
            "Generate creative business mechanisms inside fixed canonical families. "
            "Treat uncertainty as assumptions, never as verified fact."
        ),
        model=policy.creative_model,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort=policy.creative_reasoning_effort),
            verbosity="low",
            max_tokens=policy.creative_max_output_tokens,
        ),
        output_type=LiveCreativePayload,
    )
    raw = _run_structured(
        agent,
        prompt,
        gate=gate,
        model=policy.creative_model,
        max_output_tokens=policy.creative_max_output_tokens,
        runner=runner,
    )
    payload = _coerce_output(raw, LiveCreativePayload)
    assert isinstance(payload, LiveCreativePayload)
    return apply_live_creative_payload(baseline, payload)


def _expert_prompt(spec: Any, creative: CreativeEngineResult) -> str:
    ideas = [
        {
            "idea_id": item.idea_id,
            "mechanism_family": creative.mechanism_family_by_idea_id[item.idea_id],
            "title": item.title,
            "core_mechanism": item.core_mechanism,
            "customer_value": item.customer_value,
            "business_value": item.business_value,
            "assumptions": item.assumptions,
            "risks": item.risks,
        }
        for item in creative.ideas
    ]
    return (
        "Act as one independent analytical lens in MIND FORGE, not as historical-person "
        "role-play. Score every idea in the exact universe from 0 to 1. Do not coordinate "
        "with other lenses and do not infer facts that are not present. Strongest idea must "
        "be one of the supplied idea IDs.\n\n"
        f"LENS: {spec.lens}\n"
        f"GUIDING QUESTION: {spec.guiding_question}\n"
        f"KNOWN LENS ASSUMPTION TO CHALLENGE: {spec.assumption}\n"
        f"KNOWN LENS OBJECTION TO CONSIDER: {spec.objection}\n"
        f"EVIDENCE THAT COULD CHANGE THIS LENS: {spec.evidence_change}\n\n"
        f"IDEAS:\n{ideas!r}"
    )


def apply_live_expert_drafts(
    creative: CreativeEngineResult,
    drafts_by_mind_id: dict[str, LiveExpertDraft],
) -> list[ExpertMindOutput]:
    idea_ids = [item.idea_id for item in creative.ideas]
    idea_id_set = set(idea_ids)
    expected_minds = {spec.mind_id for spec in _MIND_SPECS}
    if set(drafts_by_mind_id) != expected_minds:
        raise ValueError("live expert drafts must cover exactly the ten configured minds")

    outputs: list[ExpertMindOutput] = []
    for spec in _MIND_SPECS:
        draft = drafts_by_mind_id[spec.mind_id]
        if draft.strongest_idea_id not in idea_id_set:
            raise ValueError(f"{spec.mind_id} selected an unknown strongest idea")
        if set(draft.support_scores) != idea_id_set:
            raise ValueError(f"{spec.mind_id} must score the complete idea universe")
        outputs.append(
            ExpertMindOutput(
                mind_id=spec.mind_id,
                lens=spec.lens,
                assessed_idea_ids=idea_ids,
                strongest_idea_id=draft.strongest_idea_id,
                independent_reasoning=draft.independent_reasoning,
                assumptions=draft.assumptions,
                objections=draft.objections,
                evidence_that_changes_view=draft.evidence_that_changes_view,
                support_scores=draft.support_scores,
            )
        )
    return outputs


def evaluate_with_live_expert_minds(
    creative: CreativeEngineResult,
    policy: LiveModelPolicy,
    gate: LiveBudgetGate,
    *,
    runner: RunnerCallable = Runner.run_sync,
) -> list[ExpertMindOutput]:
    assert_live_model_access(policy)
    drafts: dict[str, LiveExpertDraft] = {}
    for spec in _MIND_SPECS:
        prompt = _expert_prompt(spec, creative)
        agent = Agent(
            name=f"MIND FORGE Expert — {spec.lens}",
            instructions=(
                "Apply only the assigned analytical lens. Evaluate all ideas independently, "
                "state objections, and keep unsupported beliefs explicitly as assumptions."
            ),
            model=policy.expert_model,
            model_settings=ModelSettings(
                reasoning=Reasoning(effort=policy.expert_reasoning_effort),
                verbosity="low",
                max_tokens=policy.expert_max_output_tokens,
            ),
            output_type=LiveExpertDraft,
        )
        raw = _run_structured(
            agent,
            prompt,
            gate=gate,
            model=policy.expert_model,
            max_output_tokens=policy.expert_max_output_tokens,
            runner=runner,
        )
        draft = _coerce_output(raw, LiveExpertDraft)
        assert isinstance(draft, LiveExpertDraft)
        drafts[spec.mind_id] = draft

    return apply_live_expert_drafts(creative, drafts)
