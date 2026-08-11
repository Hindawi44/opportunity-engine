"""Bounded OpenAI advisory for fabric procurement candidates.

The advisor reads only source evidence already collected by the fabric procurement
watch. Model output is advisory, never a source of truth, and may not contact,
reserve, order, purchase or pay.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from typing import Any, Mapping, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from opportunity_engine.discovery.openai_hunt_case_enrichment import (
    OpenAIHuntCaseError,
    OpenAIResponsesHTTPClient,
)
from opportunity_engine.discovery.openai_strict_schema_compat import strict_openai_schema

SCHEMA_VERSION = "openai-fabric-procurement-advisor-1.0"
DEFAULT_MODEL = "gpt-5.6-luna"
DEFAULT_MAX_CANDIDATES = 7
MAX_CANDIDATES = 7
MAX_API_REQUESTS = 1
MAX_OUTPUT_TOKENS = 3600


class FabricProcurementAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    candidate_id: str = Field(min_length=1, max_length=300)
    review_priority: str = Field(pattern="^(HIGH|MEDIUM|LOW)$")
    material_summary: str = Field(min_length=1, max_length=900)
    source_facts: list[str] = Field(default_factory=list, max_length=6)
    missing_information: list[str] = Field(default_factory=list, max_length=8)
    operator_questions: list[str] = Field(default_factory=list, max_length=8)
    norway_import_checks: list[str] = Field(default_factory=list, max_length=6)
    reason: str = Field(min_length=1, max_length=1200)
    confidence: float = Field(ge=0, le=1)


class FabricProcurementAdvisorOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    assessments: list[FabricProcurementAssessment] = Field(default_factory=list, max_length=MAX_CANDIDATES)
    overall_note: str = Field(min_length=1, max_length=1200)


class StructuredClient(Protocol):
    def create_structured_response(
        self,
        *,
        model: str,
        instructions: str,
        input_text: str,
        schema_name: str,
        schema: Mapping[str, Any],
        reasoning_effort: str,
        max_output_tokens: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]: ...


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _bounded_int(value: object, default: int) -> int:
    try:
        return max(0, min(MAX_CANDIDATES, int(_compact(value) or default)))
    except ValueError:
        return default


def select_procurement_candidates(
    report: Mapping[str, Any], *, max_candidates: int = DEFAULT_MAX_CANDIDATES
) -> list[dict[str, Any]]:
    """Select at most one top candidate per supplier to preserve source diversity."""
    limit = max(0, min(MAX_CANDIDATES, int(max_candidates)))
    if limit == 0:
        return []
    best_by_source: dict[str, dict[str, Any]] = {}
    for candidate in _rows(report.get("candidates")):
        candidate_id = _compact(candidate.get("candidate_id"))
        source_id = _compact(candidate.get("source_id"))
        if not candidate_id or not source_id:
            continue
        current = best_by_source.get(source_id)
        score = float(candidate.get("procurement_relevance_score") or 0)
        current_score = float((current or {}).get("procurement_relevance_score") or -1)
        if current is None or score > current_score or (
            score == current_score
            and _compact(candidate.get("source_url")) < _compact(current.get("source_url"))
        ):
            best_by_source[source_id] = candidate
    selected = sorted(
        best_by_source.values(),
        key=lambda item: (
            -float(item.get("procurement_relevance_score") or 0),
            _compact(item.get("source_name")),
            _compact(item.get("candidate_id")),
        ),
    )[:limit]
    return [deepcopy(item) for item in selected]


def _input_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "candidate_id",
        "source_id",
        "source_name",
        "source_country",
        "source_kind",
        "location",
        "title",
        "description",
        "source_url",
        "fabric_terms",
        "bridal_terms",
        "value_terms",
        "price_text",
        "price",
        "currency",
        "quantity",
        "quantity_unit",
        "procurement_relevance_score",
        "verification_status",
    )
    return {key: candidate.get(key) for key in keys if candidate.get(key) is not None}


INSTRUCTIONS = """You are an advisory procurement analyst for a Norwegian tailoring operator. Analyze only the supplied fabric supplier evidence. Do not invent composition, MOQ, price, VAT treatment, shipping availability, stock quantity, certifications, lead time, or suitability. If a fact is absent, list it as missing information or an operator question. Prioritize review based on the supplied evidence only. Norway import checks are questions/checks, not claims. Keep every field concise: prefer short factual phrases over prose and avoid repeating the same missing fact in multiple fields. Never recommend automatic contact, reservation, purchase or payment. Return strict JSON and use only supplied candidate IDs."""


def _empty(
    status: str,
    *,
    model: str,
    selected_count: int,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "model": model,
        "selected_candidate_count": selected_count,
        "api_request_count": 0,
        "assessments": [],
        "overall_note": "No model advisory was produced.",
        "usage": {},
        "error": error,
        "model_output_is_advisory": True,
        "source_evidence_required_for_verification": True,
        "promotion_to_opportunity_allowed": False,
        "analysis_eligible": False,
        "top5_eligible": False,
        "automatic_contact": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def run_openai_fabric_procurement_advisor(
    report: Mapping[str, Any],
    *,
    environment: Mapping[str, str] | None = None,
    client: StructuredClient | None = None,
) -> dict[str, Any]:
    env = dict(os.environ if environment is None else environment)
    model = _compact(env.get("OPENAI_FABRIC_ADVISOR_MODEL")) or DEFAULT_MODEL
    max_candidates = _bounded_int(
        env.get("OPENAI_FABRIC_ADVISOR_MAX_CANDIDATES"), DEFAULT_MAX_CANDIDATES
    )
    selected = select_procurement_candidates(report, max_candidates=max_candidates)
    if not selected:
        return _empty(
            "NO_ELIGIBLE_CANDIDATES", model=model, selected_count=0
        )

    api_client = client
    if api_client is None:
        api_key = _compact(env.get("OPENAI_API_KEY"))
        if not api_key:
            return _empty(
                "SKIPPED_NO_API_KEY", model=model, selected_count=len(selected)
            )
        api_client = OpenAIResponsesHTTPClient(api_key)

    input_text = json.dumps(
        {"fabric_procurement_candidates": [_input_candidate(item) for item in selected]},
        ensure_ascii=False,
        sort_keys=True,
    )
    try:
        raw, usage = api_client.create_structured_response(
            model=model,
            instructions=INSTRUCTIONS,
            input_text=input_text,
            schema_name="fabric_procurement_advisor",
            schema=strict_openai_schema(FabricProcurementAdvisorOutput),
            reasoning_effort="low",
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
        parsed = FabricProcurementAdvisorOutput.model_validate(raw)
    except (OpenAIHuntCaseError, ValidationError, TypeError, ValueError) as exc:
        return _empty(
            "FAILED",
            model=model,
            selected_count=len(selected),
            error=f"{type(exc).__name__}: {_compact(exc)[:500]}",
        )

    selected_ids = {_compact(item.get("candidate_id")) for item in selected}
    seen: set[str] = set()
    assessments: list[dict[str, Any]] = []
    for assessment in parsed.assessments:
        candidate_id = _compact(assessment.candidate_id)
        if candidate_id not in selected_ids or candidate_id in seen:
            continue
        seen.add(candidate_id)
        assessments.append(assessment.model_dump())

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "model": model,
        "selected_candidate_count": len(selected),
        "selected_candidate_ids": sorted(selected_ids),
        "api_request_count": 1,
        "assessment_count": len(assessments),
        "assessments": assessments,
        "overall_note": parsed.overall_note,
        "usage": dict(usage),
        "error": None,
        "model_output_is_advisory": True,
        "source_evidence_required_for_verification": True,
        "promotion_to_opportunity_allowed": False,
        "analysis_eligible": False,
        "top5_eligible": False,
        "automatic_contact": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def attach_advisory_to_fabric_report(
    report: Mapping[str, Any], advisor: Mapping[str, Any]
) -> dict[str, Any]:
    """Attach validated advisory metadata to matching fabric rows for river ingestion."""
    result = deepcopy(dict(report))
    by_id = {
        _compact(item.get("candidate_id")): dict(item)
        for item in _rows(advisor.get("assessments"))
        if _compact(item.get("candidate_id"))
    }
    candidates = result.get("candidates")
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            assessment = by_id.get(_compact(candidate.get("candidate_id")))
            if not assessment:
                continue
            metadata = candidate.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
                candidate["metadata"] = metadata
            metadata["openai_procurement_advisory"] = assessment
    result["openai_procurement_advisor"] = {
        "schema_version": advisor.get("schema_version"),
        "status": advisor.get("status"),
        "model": advisor.get("model"),
        "api_request_count": advisor.get("api_request_count", 0),
        "assessment_count": advisor.get("assessment_count", 0),
        "model_output_is_advisory": True,
    }
    return result
