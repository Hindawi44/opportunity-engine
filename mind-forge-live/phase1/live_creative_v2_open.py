from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from agents import Agent, ModelSettings, Runner
from openai.types.shared import Reasoning

from .contracts_v1 import Question, TopicInput
from .creative_engine_v1 import CreativeEngineResult
from .creative_engine_v2_open import OpenCreativePayload, apply_open_payload, open_creative_prompt
from .live_model_adapter_v1 import (
    LiveBudgetGate,
    LiveModelPolicy,
    RunnerCallable,
    _coerce_output,
    _run_structured,
    assert_live_model_access,
)


def generate_live_open_ideas(
    topic: TopicInput,
    questions: Iterable[Question],
    policy: LiveModelPolicy,
    gate: LiveBudgetGate,
    *,
    runner: RunnerCallable = Runner.run_sync,
) -> CreativeEngineResult:
    """Paid Creative Engine V2: generate the idea universe from the seed/questions themselves."""

    assert_live_model_access(policy)
    question_list = list(questions)
    prompt = open_creative_prompt(topic, question_list)
    agent = Agent(
        name="MIND FORGE Creative Engine V2 Open",
        instructions=(
            "Invent the idea universe from the topic itself. Do not preserve, rewrite, or "
            "imitate any hidden canonical family list. Keep unsupported claims as assumptions."
        ),
        model=policy.creative_model,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort=policy.creative_reasoning_effort),
            verbosity="low",
            max_tokens=policy.creative_max_output_tokens,
        ),
        output_type=OpenCreativePayload,
    )
    raw: Any = _run_structured(
        agent,
        prompt,
        gate=gate,
        model=policy.creative_model,
        max_output_tokens=policy.creative_max_output_tokens,
        runner=runner,
    )
    payload = _coerce_output(raw, OpenCreativePayload)
    assert isinstance(payload, OpenCreativePayload)
    return apply_open_payload(topic, question_list, payload)
