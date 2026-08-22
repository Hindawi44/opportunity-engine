from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agents import Agent, ModelSettings, Runner, WebSearchTool
from pydantic import BaseModel, ConfigDict, Field


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
    observation_text: str = Field(min_length=1, max_length=1500)
    stance: str = Field(pattern="^(SUPPORTS|CONTRADICTS|MIXED|NEUTRAL)$")
    confidence: float = Field(ge=0.0, le=0.90)


class _ResearchDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observations: list[_ObservationDraft] = Field(default_factory=list, max_length=3)


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


def _build_plan(reasoning: dict[str, Any]) -> list[dict[str, Any]]:
    selected = list(reasoning.get("selected_idea_ids", []) or [])
    assessments = {str(row["idea_id"]): row for row in reasoning.get("assessments", []) or []}
    if len(selected) != 3:
        raise ValueError(f"live evidence requires exactly three selected ideas, got {len(selected)}")
    plan: list[dict[str, Any]] = []
    for rank, idea_id in enumerate(selected, start=1):
        idea_id = str(idea_id)
        row = assessments.get(idea_id)
        if row is None:
            raise ValueError(f"selected idea missing from assessments: {idea_id}")
        critique = row.get("critique", {}) or {}
        claim = str(critique.get("key_assumption") or critique.get("key_risk") or "").strip()
        if not claim:
            claim = f"There is a real material need in Norway for {row.get('title') or idea_id}."
        plan.append({
            "request_id": f"v2-top3-{rank}",
            "idea_id": idea_id,
            "title": str(row.get("title") or idea_id),
            "claim_text": claim,
        })
    return plan


def _prompt(request: dict[str, Any]) -> str:
    return (
        "You are the bounded Evidence collector for MIND FORGE Creative V2. Perform one web search only. "
        "Prefer Norwegian official/public/primary sources when available. Return at most three observations, "
        "and every source_ref must be an exact URL from the web-search sources. Do not make the final business "
        "decision. Stance must be SUPPORTS, CONTRADICTS, MIXED, or NEUTRAL relative to the exact claim.\n\n"
        f"IDEA: {request['title']}\nCLAIM: {request['claim_text']}\nMARKET: Norway"
    )


def _research_one(request: dict[str, Any], *, model: str) -> tuple[list[dict[str, Any]], int]:
    agent = Agent(
        name=f"MIND FORGE V2 Evidence {request['request_id']}",
        instructions="Collect sourced observations only and preserve exact source URLs.",
        model=model,
        tools=[WebSearchTool(search_context_size="low")],
        model_settings=ModelSettings(
            tool_choice="required",
            parallel_tool_calls=False,
            max_tokens=700,
            verbosity="low",
            response_include=["web_search_call.action.sources"],
        ),
        output_type=_ResearchDraft,
    )
    result = Runner.run_sync(agent, _prompt(request), max_turns=2)
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
        stances: set[str] = set()
        refs: list[str] = []
        for obs in by_idea[idea_id]:
            stance = str(obs["stance"]).upper()
            confidence = float(obs["confidence"])
            quality = _SOURCE_WEIGHTS.get(str(obs.get("source_type", "unknown")), 0.35)
            weight = quality * confidence
            weighted_sum += _STANCE_SIGN[stance] * weight
            weight_total += weight
            stances.add(stance)
            refs.append(str(obs["source_ref"]))
        signal = max(-1.0, min(1.0, weighted_sum / weight_total)) if weight_total else 0.0
        evidence_score = _bounded((signal + 1.0) / 2.0)
        conflict = "SUPPORTS" in stances and "CONTRADICTS" in stances
        final_score = _bounded(0.70 * base + 0.30 * evidence_score - (0.08 if conflict else 0.0))
        rows.append({
            "idea_id": idea_id,
            "title": assessments[idea_id].get("title"),
            "reasoning_score": round(base, 4),
            "evidence_score": evidence_score,
            "evidence_signal": round(signal, 4),
            "evidence_count": len(by_idea[idea_id]),
            "conflicting_evidence": conflict,
            "final_score": final_score,
            "source_refs": refs,
        })
    ranked = sorted(rows, key=lambda row: (row["final_score"], row["reasoning_score"], row["idea_id"]), reverse=True)
    return {
        "status": "MIND_FORGE_V2_FINAL_RANK_COMPLETE",
        "uses_mechanism_family_for_scoring": False,
        "ranking": ranked,
        "selected_idea_ids": [row["idea_id"] for row in ranked],
        "selected_titles": [row["title"] for row in ranked],
    }


def run_live_top3_evidence(reasoning: dict[str, Any], *, model: str = "gpt-5.6-luna") -> dict[str, Any]:
    plan = _build_plan(reasoning)
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
    out_dir = Path("artifacts/mind-forge-creative-v2-open-live")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "evidence.json").write_text(
        json.dumps({"observations": all_observations}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "final_rank.json").write_text(json.dumps(final_rank, ensure_ascii=False, indent=2), encoding="utf-8")
    usage = {
        "search_operations": search_operations,
        "estimated_research_cost_usd": estimated_cost_usd,
        "hard_search_operation_cap": 3,
        "hard_estimated_cost_cap_usd": 0.03,
    }
    (out_dir / "live_evidence_usage.json").write_text(json.dumps(usage, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"usage": usage, "final_rank": final_rank, "observations": all_observations}
