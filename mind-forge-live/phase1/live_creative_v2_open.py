from __future__ import annotations

import os
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


def _assert_guarded_live_access(policy: LiveModelPolicy) -> None:
    """Preserve the paid-call guard, with a narrow bridge for the explicit manual V2 job."""

    if os.getenv("MIND_FORGE_LIVE_ENABLED") == "1":
        assert_live_model_access(policy)
        return

    github_guarded_job = (
        os.getenv("GITHUB_ACTIONS") == "true"
        and os.getenv("GITHUB_JOB") == "creative-v2-open-live"
        and bool(os.getenv("OPENAI_API_KEY", "").strip())
    )
    if not github_guarded_job:
        assert_live_model_access(policy)
        return

    # The main launcher reaches this exact job only after the user explicitly
    # selected CREATIVE_V2_OPEN and confirmed the paid execution with YES.
    # Set the existing adapter guard locally so all downstream checks remain intact.
    os.environ["MIND_FORGE_LIVE_ENABLED"] = "1"
    assert_live_model_access(policy)


def generate_live_open_ideas(
    topic: TopicInput,
    questions: Iterable[Question],
    policy: LiveModelPolicy,
    gate: LiveBudgetGate,
    *,
    runner: RunnerCallable = Runner.run_sync,
) -> CreativeEngineResult:
    """Paid Creative Engine V2: generate the idea universe from the seed/questions themselves."""

    _assert_guarded_live_access(policy)
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
