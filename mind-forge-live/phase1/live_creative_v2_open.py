from __future__ import annotations

import json
import math
import os
from collections.abc import Iterable
from pathlib import Path
from statistics import mean
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


_REASONING_LENSES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("systems_scale", "Systems & Scale", ("scale", "repeat", "standard", "capacity", "network")),
    ("information_edge", "Information Advantage", ("signal", "data", "forecast", "trace", "verify")),
    ("capital", "Capital Allocation", ("margin", "cost", "inventory", "cash", "capital", "preorder")),
    ("retail", "Retail Efficiency", ("stock", "merchant", "order", "delivery", "customer")),
    ("operations", "Operational Productivity", ("process", "workflow", "routing", "inspection", "handling")),
    ("standardization", "Standardization", ("standard", "procedure", "repeatable", "package", "specification")),
    ("distribution", "Distribution", ("route", "delivery", "supplier", "fulfillment", "access")),
    ("customer_trust", "Customer Trust", ("trust", "warranty", "clarity", "evidence", "origin", "compliance")),
    ("replication", "Replication", ("shared", "recurring", "operator", "business", "replenishment")),
    ("differentiation", "Differentiation", ("novel", "alternative", "repair", "service", "substitute", "outcome")),
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

    os.environ["MIND_FORGE_LIVE_ENABLED"] = "1"
    assert_live_model_access(policy)


def _idea_text(idea: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("title", "core_mechanism", "customer_value", "business_value", "novelty_reason"):
        parts.append(str(idea.get(key, "")))
    for key in ("required_capabilities", "assumptions", "risks"):
        parts.extend(str(item) for item in idea.get(key, []) or [])
    return " ".join(parts).casefold()


def _bounded(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def _structural_quality(idea: dict[str, Any]) -> float:
    required = len(idea.get("required_capabilities", []) or [])
    assumptions = len(idea.get("assumptions", []) or [])
    risks = len(idea.get("risks", []) or [])
    completeness = mean(
        1.0 if str(idea.get(key, "")).strip() else 0.0
        for key in ("core_mechanism", "customer_value", "business_value", "novelty_reason")
    )
    simplicity = 1.0 - min(required, 6) / 8.0
    assumption_burden = min(assumptions, 5) / 5.0
    risk_burden = min(risks, 5) / 5.0
    return _bounded(
        0.50 * completeness
        + 0.30 * simplicity
        + 0.10 * (1.0 - assumption_burden)
        + 0.10 * (1.0 - risk_burden)
    )


def _lens_score(idea: dict[str, Any], keywords: tuple[str, ...]) -> float:
    text = _idea_text(idea)
    hits = sum(1 for keyword in keywords if keyword in text)
    semantic = min(1.0, hits / max(2, math.ceil(len(keywords) / 2)))
    return _bounded(0.55 * _structural_quality(idea) + 0.45 * semantic)


def _logic_score(idea: dict[str, Any]) -> float:
    required = len(idea.get("required_capabilities", []) or [])
    assumptions = len(idea.get("assumptions", []) or [])
    risks = len(idea.get("risks", []) or [])
    feasibility = 1.0 - min(required, 6) / 9.0
    reversibility = 0.78 if any(
        word in _idea_text(idea) for word in ("test", "preorder", "small", "pilot", "limited")
    ) else 0.62
    dependency_risk = min(1.0, 0.18 * required + 0.12 * risks)
    evidence_debt = min(1.0, 0.16 * assumptions + 0.08 * risks)
    simplicity = 1.0 - min(required, 6) / 6.0
    return _bounded(
        0.30 * feasibility
        + 0.20 * reversibility
        + 0.20 * (1.0 - dependency_risk)
        + 0.20 * (1.0 - evidence_debt)
        + 0.10 * simplicity
    )


def _critique(idea: dict[str, Any], logic_score: float) -> dict[str, Any]:
    assumptions = list(idea.get("assumptions", []) or [])
    risks = list(idea.get("risks", []) or [])
    severity = _bounded(0.30 + 0.08 * len(assumptions) + 0.07 * len(risks) + 0.25 * (1.0 - logic_score))
    if severity >= 0.72:
        disposition = "REWORK"
    elif severity >= 0.56:
        disposition = "NEEDS_EVIDENCE"
    else:
        disposition = "SURVIVES"
    key_assumption = assumptions[0] if assumptions else "The mechanism creates measurable customer and business value."
    key_risk = risks[0] if risks else "Execution complexity may exceed the expected value."
    return {
        "severity": severity,
        "disposition": disposition,
        "key_assumption": key_assumption,
        "key_risk": key_risk,
        "falsification_test": f"Run the smallest reversible test that directly challenges: {key_assumption}",
    }


def _evaluate_family_agnostic_reasoning(
    topic: TopicInput,
    creative: CreativeEngineResult,
    *,
    top_n: int = 3,
) -> dict[str, Any]:
    """Run ten fixed analytical lenses without using mechanism-family labels for scoring."""

    ideas = [idea.model_dump(mode="json") for idea in creative.ideas]
    if len(_REASONING_LENSES) != 10:
        raise RuntimeError("reasoning pipeline requires exactly ten lenses")

    scores_by_idea: dict[str, list[float]] = {str(idea["idea_id"]): [] for idea in ideas}
    expert_outputs: list[dict[str, Any]] = []
    for lens_id, label, keywords in _REASONING_LENSES:
        scores = {str(idea["idea_id"]): _lens_score(idea, keywords) for idea in ideas}
        strongest = max(scores, key=lambda idea_id: (scores[idea_id], idea_id))
        expert_outputs.append(
            {
                "lens_id": lens_id,
                "lens": label,
                "strongest_idea_id": strongest,
                "support_scores": scores,
            }
        )
        for idea_id, score in scores.items():
            scores_by_idea[idea_id].append(score)

    assessments: list[dict[str, Any]] = []
    for idea in ideas:
        idea_id = str(idea["idea_id"])
        logic = _logic_score(idea)
        expert_mean = _bounded(mean(scores_by_idea[idea_id]))
        critique = _critique(idea, logic)
        composite = _bounded(0.62 * logic + 0.38 * expert_mean - 0.12 * critique["severity"])
        assessments.append(
            {
                "idea_id": idea_id,
                "title": idea.get("title"),
                "mechanism_family": creative.mechanism_family_by_idea_id.get(idea_id),
                "logic_score": logic,
                "expert_support_mean": expert_mean,
                "critique": critique,
                "composite_score": composite,
            }
        )

    ranked = sorted(
        assessments,
        key=lambda row: (row["composite_score"], row["logic_score"], row["idea_id"]),
        reverse=True,
    )
    selected = [
        row["idea_id"]
        for row in ranked
        if row["critique"]["disposition"] != "REWORK"
    ][:top_n]
    if len(selected) < min(top_n, len(ranked)):
        selected = [row["idea_id"] for row in ranked[:top_n]]

    titles = {str(idea["idea_id"]): str(idea.get("title", "")) for idea in ideas}
    return {
        "status": "MIND_FORGE_V2_REASONING_COMPLETE",
        "seed": topic.topic,
        "idea_count": len(ideas),
        "expert_mind_count": len(expert_outputs),
        "uses_mechanism_family_for_scoring": False,
        "expert_outputs": expert_outputs,
        "assessments": ranked,
        "selected_idea_ids": selected,
        "selected_titles": [titles[idea_id] for idea_id in selected],
    }


def _write_live_reasoning_artifact(topic: TopicInput, creative: CreativeEngineResult) -> None:
    """Attach reasoning and bounded live evidence only to the explicit Creative V2 GitHub job."""

    if not (
        os.getenv("GITHUB_ACTIONS") == "true"
        and os.getenv("GITHUB_JOB") == "creative-v2-open-live"
    ):
        return

    result = _evaluate_family_agnostic_reasoning(topic, creative, top_n=3)
    out_dir = Path("artifacts/mind-forge-creative-v2-open-live")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "reasoning.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "top3.json").write_text(
        json.dumps(
            {
                "selected_idea_ids": result["selected_idea_ids"],
                "selected_titles": result["selected_titles"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    from scripts.mind_forge_v2_live_evidence_runtime import run_live_top3_evidence

    live_result = run_live_top3_evidence(
        result,
        model=os.getenv("MIND_FORGE_RESEARCH_MODEL", "gpt-5.6-luna"),
    )
    print(
        json.dumps(
            {
                "status": "MIND_FORGE_V2_TOP3_LIVE_EVIDENCE_COMPLETE",
                "search_operations": live_result["usage"]["search_operations"],
                "estimated_research_cost_usd": live_result["usage"]["estimated_research_cost_usd"],
                "selected_titles": live_result["final_rank"]["selected_titles"],
            },
            ensure_ascii=False,
        )
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
    creative = apply_open_payload(topic, question_list, payload)
    _write_live_reasoning_artifact(topic, creative)
    return creative
