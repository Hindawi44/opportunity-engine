from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agents import Agent, ModelSettings, Runner, WebSearchTool
from pydantic import BaseModel, ConfigDict, Field

from scripts.mind_forge_v2_fast_learning_memory import learn_from_run
from scripts.mind_forge_v2_top3_research_plan import build_top3_research_plan


_SOURCE_WEIGHTS = {
    "official": 1.00,
    "public_data": 1.00,
    "primary": 0.95,
    "academic": 0.90,
    "industry": 0.80,
    "company": 0.65,
    "secondary": 0.55,
    "unknown": 0.35,
}
_STANCE_SIGN = {"SUPPORTS": 1.0, "CONTRADICTS": -1.0, "MIXED": -0.25, "NEUTRAL": 0.0}
_RELEVANCE_WEIGHTS = {
    "DIRECT": 1.00,
    "ADJACENT": 0.35,
    "GENERIC": 0.00,
    "OFF_DOMAIN": 0.00,
}
_OFFICIAL_HOSTS = {
    "brreg.no",
    "www.brreg.no",
    "virksomhet.brreg.no",
    "skatteetaten.no",
    "www.skatteetaten.no",
    "altinn.no",
    "www.altinn.no",
    "ssb.no",
    "www.ssb.no",
    "mattilsynet.no",
    "www.mattilsynet.no",
    "regjeringen.no",
    "www.regjeringen.no",
    "nav.no",
    "www.nav.no",
}


class _ObservationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ref: str = Field(min_length=1)
    observation_text: str = Field(min_length=1, max_length=360)
    stance: str = Field(pattern="^(SUPPORTS|CONTRADICTS|MIXED|NEUTRAL)$")
    confidence: float = Field(ge=0.0, le=0.90)
    relevance: str = Field(pattern="^(DIRECT|ADJACENT|GENERIC|OFF_DOMAIN)$")
    relevance_reason: str = Field(min_length=1, max_length=240)


class _ResearchDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observations: list[_ObservationDraft] = Field(default_factory=list, max_length=2)


def _jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonish(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonish(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _jsonish(getattr(value, field.name)) for field in fields(value)}
    if hasattr(value, "model_dump"):
        try:
            return _jsonish(value.model_dump(mode="json"))
        except TypeError:
            return _jsonish(value.model_dump())
    return value


def _walk(value: Any):
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _count_search_calls(payloads: list[Any]) -> int:
    count = 0
    for payload in payloads:
        for row in _walk(payload):
            if row.get("type") == "web_search_call":
                count += 1
    return count


def _extract_sources(payloads: list[Any]) -> dict[str, str]:
    sources: dict[str, str] = {}
    for payload in payloads:
        for row in _walk(payload):
            url = row.get("url")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                continue
            title = row.get("title")
            if not isinstance(title, str) or not title.strip():
                title = urlparse(url).netloc or url
            sources.setdefault(url, title.strip())
    return sources


def _source_type(url: str) -> str:
    host = urlparse(url).netloc.casefold()
    if host in _OFFICIAL_HOSTS or host.endswith(".kommune.no"):
        return "official"
    if host.endswith(".edu") or host.endswith(".ac.uk"):
        return "academic"
    if "data.norge.no" in host:
        return "public_data"
    return "primary"


def _load_prior_memory(explicit: dict[str, Any] | None) -> dict[str, Any] | None:
    if explicit is not None:
        return dict(explicit)
    path_text = os.getenv("MIND_FORGE_PRIOR_MEMORY_PATH", "").strip()
    if not path_text:
        return None
    path = Path(path_text)
    if not path.is_file():
        raise ValueError(f"MIND_FORGE_PRIOR_MEMORY_PATH does not exist: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("prior fast-learning memory must be a JSON object")
    return data


def _build_plan(
    reasoning: dict[str, Any],
    prior_memory: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    topic = str(reasoning.get("seed") or "").strip()
    if not topic:
        raise ValueError("live evidence requires the original topic/seed for relevance checking")

    research_plan = build_top3_research_plan(reasoning, prior_memory)
    requests = list(research_plan.get("requests", []) or [])
    if len(requests) != 3:
        raise ValueError(f"live evidence requires exactly three selected ideas, got {len(requests)}")

    plan: list[dict[str, Any]] = []
    for row in requests:
        request = dict(row)
        request["topic"] = topic
        plan.append(request)
    return plan


def _prompt(request: dict[str, Any]) -> str:
    hints = list(request.get("shadow_search_hints", []) or [])
    memory_block = ""
    if hints:
        lines = []
        for hint in hints:
            action = str(hint.get("action") or "").strip()
            question = str(hint.get("search_question") or "").strip()
            required = str(hint.get("required_evidence") or "").strip()
            if not question or not required:
                continue
            lines.append(f"- {action}: {question} Required evidence: {required}")
        if lines:
            memory_block = (
                "\n\nPRIOR CROSS-RUN LEARNING — search guidance only. "
                "It is not evidence, cannot reject an idea, and cannot override the exact current claim.\n"
                + "\n".join(lines)
            )

    return (
        "You are the bounded Evidence collector for MIND FORGE Creative V2. Perform exactly one web search. "
        "Prefer Norwegian official/public/primary sources. Return only one or two grounded observations in the schema. "
        "Keep every observation_text under 240 characters. Every source_ref must be an exact URL from web-search sources. "
        "Do not explain your process and do not make the final business decision. Stance must be SUPPORTS, CONTRADICTS, "
        "MIXED, or NEUTRAL relative to the exact claim.\n\n"
        "For every observation, classify evidence relevance conservatively:\n"
        "- DIRECT: same real-world topic/domain as TOPIC and materially tests the exact CLAIM.\n"
        "- ADJACENT: same topic/domain but only an indirect proxy for the CLAIM.\n"
        "- GENERIC: broad statistics, policy, right-to-repair, or general business/repair material that does not establish "
        "the claim in this topic.\n"
        "- OFF_DOMAIN: evidence about a different product, service, or industry.\n"
        "Do not label evidence DIRECT merely because the source is official or contains a generic word such as repair. "
        "If the search finds only generic or off-domain evidence, return it with that relevance label rather than forcing "
        "a supportive conclusion. Give a short relevance_reason explaining the domain match or mismatch."
        f"{memory_block}\n\n"
        f"TOPIC: {request['topic']}\n"
        f"IDEA: {request['title']}\n"
        f"CLAIM: {request['claim_text']}\n"
        "MARKET: Norway"
    )


def _research_one(request: dict[str, Any], *, model: str) -> tuple[list[dict[str, Any]], int]:
    agent = Agent(
        name=f"MIND FORGE V2 Evidence {request['request_id']}",
        instructions=(
            "Collect concise sourced observations only; preserve exact source URLs; classify domain relevance "
            "conservatively; no prose outside the schema."
        ),
        model=model,
        tools=[WebSearchTool(search_context_size="low")],
        model_settings=ModelSettings(
            tool_choice="required",
            parallel_tool_calls=False,
            max_tokens=1200,
            verbosity="low",
            response_include=["web_search_call.action.sources"],
        ),
        output_type=_ResearchDraft,
    )
    result = Runner.run_sync(agent, _prompt(request), max_turns=1)
    raw_payloads = [_jsonish(item) for item in getattr(result, "raw_responses", [])]
    item_payloads = [
        _jsonish(raw_item)
        for item in getattr(result, "new_items", [])
        if (raw_item := getattr(item, "raw_item", None)) is not None
    ]
    operations = max(_count_search_calls(raw_payloads), _count_search_calls(item_payloads))
    sources = _extract_sources(raw_payloads) or _extract_sources(item_payloads)
    if sources:
        operations = max(operations, 1)
    if operations != 1:
        raise RuntimeError(f"Top 3 evidence request must use exactly one web search operation, got {operations}")
    if not sources:
        raise RuntimeError("Top 3 evidence search returned no source URLs; fail closed")

    draft = result.final_output
    if not isinstance(draft, _ResearchDraft):
        draft = _ResearchDraft.model_validate(draft)

    observations: list[dict[str, Any]] = []
    for item in draft.observations:
        if item.source_ref not in sources:
            continue
        observations.append({
            "idea_id": request["idea_id"],
            "stance": item.stance,
            "confidence": item.confidence,
            "relevance": item.relevance,
            "relevance_reason": item.relevance_reason,
            "source_type": _source_type(item.source_ref),
            "source_ref": item.source_ref,
            "source": sources[item.source_ref],
            "observation_text": item.observation_text,
        })
    if not observations:
        raise RuntimeError("Top 3 evidence search produced no grounded observations; fail closed")
    return observations, operations


def _bounded(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def _rerank(reasoning: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
    selected = [str(item) for item in reasoning.get("selected_idea_ids", []) or []]
    assessments = {str(row["idea_id"]): row for row in reasoning.get("assessments", []) or []}
    by_idea: dict[str, list[dict[str, Any]]] = {idea_id: [] for idea_id in selected}
    for obs in observations:
        idea_id = str(obs["idea_id"])
        if idea_id not in by_idea:
            raise ValueError(f"evidence references idea outside Top 3: {idea_id}")
        by_idea[idea_id].append(obs)

    rows: list[dict[str, Any]] = []
    for idea_id in selected:
        base = float(assessments[idea_id].get("composite_score", 0.0))
        weighted_sum = 0.0
        weight_total = 0.0
        relevant_stances: set[str] = set()
        refs: list[str] = []
        relevant_refs: list[str] = []
        relevant_count = 0
        rejected_relevance_count = 0

        for obs in by_idea[idea_id]:
            stance = str(obs["stance"]).upper()
            confidence = float(obs["confidence"])
            quality = _SOURCE_WEIGHTS.get(str(obs.get("source_type", "unknown")), 0.35)
            relevance = str(obs.get("relevance") or "GENERIC").upper()
            relevance_weight = _RELEVANCE_WEIGHTS.get(relevance, 0.0)
            source_ref = str(obs["source_ref"])
            refs.append(source_ref)

            if relevance_weight <= 0.0:
                rejected_relevance_count += 1
                continue

            relevant_count += 1
            relevant_refs.append(source_ref)
            relevant_stances.add(stance)
            weight = quality * confidence * relevance_weight
            weighted_sum += _STANCE_SIGN[stance] * weight
            weight_total += weight

        signal = max(-1.0, min(1.0, weighted_sum / weight_total)) if weight_total else 0.0
        evidence_strength = min(1.0, weight_total)
        evidence_score = _bounded(0.5 + 0.5 * signal * evidence_strength)
        evidence_status = (
            "SUFFICIENT_RELEVANT_EVIDENCE" if relevant_count > 0 and weight_total > 0.0
            else "INSUFFICIENT_EVIDENCE"
        )
        conflict = "SUPPORTS" in relevant_stances and "CONTRADICTS" in relevant_stances

        if evidence_status == "INSUFFICIENT_EVIDENCE":
            final_score = _bounded(base)
        else:
            final_score = _bounded(0.70 * base + 0.30 * evidence_score - (0.08 if conflict else 0.0))

        rows.append({
            "idea_id": idea_id,
            "title": assessments[idea_id].get("title"),
            "reasoning_score": round(base, 4),
            "evidence_status": evidence_status,
            "evidence_score": evidence_score,
            "evidence_signal": round(signal, 4),
            "evidence_strength": round(evidence_strength, 4),
            "evidence_count": len(by_idea[idea_id]),
            "relevant_evidence_count": relevant_count,
            "rejected_relevance_count": rejected_relevance_count,
            "conflicting_evidence": conflict,
            "final_score": final_score,
            "source_refs": refs,
            "relevant_source_refs": relevant_refs,
        })

    ranked = sorted(rows, key=lambda row: (row["final_score"], row["reasoning_score"], row["idea_id"]), reverse=True)
    return {
        "status": "MIND_FORGE_V2_FINAL_RANK_COMPLETE",
        "uses_mechanism_family_for_scoring": False,
        "evidence_relevance_gate": "ENFORCED",
        "ranking": ranked,
        "selected_idea_ids": [row["idea_id"] for row in ranked],
        "selected_titles": [row["title"] for row in ranked],
    }


def run_live_top3_evidence(
    reasoning: dict[str, Any],
    *,
    model: str = "gpt-5.6-luna",
    prior_memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prior_memory = _load_prior_memory(prior_memory)
    plan = _build_plan(reasoning, prior_memory=prior_memory)
    all_observations: list[dict[str, Any]] = []
    search_operations = 0
    for request in plan:
        observations, operations = _research_one(request, model=model)
        search_operations += operations
        if search_operations > 3:
            raise RuntimeError("Top 3 live evidence exceeded three search operations")
        all_observations.extend(observations)
    estimated_cost_usd = round(search_operations * 0.01, 8)
    if search_operations != 3 or estimated_cost_usd > 0.03:
        raise RuntimeError("Top 3 live evidence budget contract violated")

    final_rank = _rerank(reasoning, all_observations)
    run_id = str(os.getenv("GITHUB_RUN_ID") or os.getenv("MIND_FORGE_RUN_ID") or "local-live-run")
    fast_memory = learn_from_run(
        reasoning,
        {"observations": all_observations},
        final_rank,
        run_id=run_id,
        prior_memory=prior_memory,
    )

    out_dir = Path("artifacts/mind-forge-creative-v2-open-live")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "evidence.json").write_text(
        json.dumps({"observations": all_observations}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "final_rank.json").write_text(json.dumps(final_rank, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "fast_learning_memory.json").write_text(
        json.dumps(fast_memory, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    usage = {
        "search_operations": search_operations,
        "estimated_research_cost_usd": estimated_cost_usd,
        "hard_search_operation_cap": 3,
        "hard_estimated_cost_cap_usd": 0.03,
        "prior_memory_loaded": bool(prior_memory),
        "fast_learning_pattern_count": len(fast_memory.get("patterns", []) or []),
    }
    (out_dir / "live_evidence_usage.json").write_text(json.dumps(usage, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "usage": usage,
        "final_rank": final_rank,
        "observations": all_observations,
        "fast_learning_memory": fast_memory,
    }
