"""OpenAI Responses API compatibility for bounded hunt-case enrichment.

This module keeps the existing hunt-case implementation narrow while enforcing
strict Structured Outputs and robustly decoding non-streaming Responses API
output. It does not change lifecycle decisions or allow model output to promote
an opportunity.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

import requests
from pydantic import BaseModel


TRIAGE_MIN_OUTPUT_TOKENS = 2400
DEEP_MIN_OUTPUT_TOKENS = 1800


def _normalize_schema_node(value: object) -> object:
    if isinstance(value, list):
        return [_normalize_schema_node(item) for item in value]
    if not isinstance(value, Mapping):
        return value

    node: dict[str, Any] = {}
    for key, item in value.items():
        if key in {"title", "default"}:
            continue
        node[str(key)] = _normalize_schema_node(item)

    if node.get("type") == "object":
        properties = node.get("properties")
        if isinstance(properties, Mapping):
            node["required"] = list(properties.keys())
        node["additionalProperties"] = False
    return node


def strict_openai_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Return a strict Responses API-compatible schema for a Pydantic model."""
    schema = _normalize_schema_node(model.model_json_schema())
    if not isinstance(schema, dict):
        raise TypeError("Structured-output schema must be an object")
    return schema


def _assert_strict_object_schema(schema: Mapping[str, Any]) -> None:
    properties = schema.get("properties")
    required = schema.get("required")
    if not isinstance(properties, Mapping):
        raise RuntimeError("Strict schema object is missing properties")
    if required != list(properties.keys()):
        raise RuntimeError("Strict schema required fields do not match properties")
    if schema.get("additionalProperties") is not False:
        raise RuntimeError("Strict schema must reject additional properties")


def _output_text_parts(raw: Mapping[str, Any]) -> list[str]:
    top_level = raw.get("output_text")
    if isinstance(top_level, str) and top_level.strip():
        return [top_level]

    parts: list[str] = []
    output = raw.get("output")
    if not isinstance(output, list):
        return parts
    for item in output:
        if not isinstance(item, Mapping) or item.get("type") != "message":
            continue
        content_items = item.get("content")
        if not isinstance(content_items, list):
            continue
        for content in content_items:
            if not isinstance(content, Mapping):
                continue
            if content.get("type") != "output_text":
                continue
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    return parts


def _decode_structured_object(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```") and candidate.endswith("```"):
        first_newline = candidate.find("\n")
        if first_newline >= 0:
            candidate = candidate[first_newline + 1 : -3].strip()

    try:
        value: object = json.loads(candidate)
        if isinstance(value, str):
            value = json.loads(value)
    except json.JSONDecodeError as first_error:
        start = candidate.find("{")
        if start < 0:
            raise first_error
        value, end = json.JSONDecoder().raw_decode(candidate[start:])
        trailing = candidate[start + end :].strip()
        if trailing and trailing != "```":
            raise first_error

    if not isinstance(value, dict):
        raise TypeError("OpenAI structured output must be an object")
    return value


def _response_reason(raw: Mapping[str, Any]) -> str:
    details = raw.get("incomplete_details")
    if isinstance(details, Mapping):
        reason = details.get("reason")
        if reason:
            return str(reason)
    error = raw.get("error")
    if isinstance(error, Mapping):
        message = error.get("message") or error.get("code")
        if message:
            return str(message)
    return "unknown"


def _compat_create_structured_response(
    self: object,
    *,
    model: str,
    instructions: str,
    input_text: str,
    schema_name: str,
    schema: Mapping[str, Any],
    reasoning_effort: str,
    max_output_tokens: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Send one bounded request and decode all returned output-text segments."""
    from opportunity_engine.discovery.openai_hunt_case_enrichment import (
        OpenAIHuntCaseError,
    )

    is_triage = schema_name == "market_hunt_case_triage"
    effective_max_output_tokens = max(
        max_output_tokens,
        TRIAGE_MIN_OUTPUT_TOKENS if is_triage else DEEP_MIN_OUTPUT_TOKENS,
    )
    effective_reasoning_effort = "none" if is_triage else "low"

    payload = {
        "model": model,
        "store": False,
        "instructions": instructions,
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": input_text}],
            }
        ],
        "reasoning": {"effort": effective_reasoning_effort},
        "text": {
            "verbosity": "low",
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": dict(schema),
            },
        },
        "max_output_tokens": effective_max_output_tokens,
    }

    session = getattr(self, "session", None) or requests
    response = session.post(
        getattr(self, "endpoint"),
        headers={
            "Authorization": f"Bearer {getattr(self, 'api_key')}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=getattr(self, "timeout_seconds"),
    )
    try:
        response.raise_for_status()
        raw = response.json()
    except (requests.RequestException, ValueError) as exc:
        detail = ""
        try:
            error_payload = response.json()
            if isinstance(error_payload, Mapping):
                error = error_payload.get("error")
                if isinstance(error, Mapping):
                    detail = str(error.get("message") or error.get("code") or "")
        except (ValueError, AttributeError):
            detail = ""
        suffix = f": {detail[:500]}" if detail else ""
        raise OpenAIHuntCaseError(f"OpenAI request failed{suffix}") from exc

    if not isinstance(raw, Mapping):
        raise OpenAIHuntCaseError("OpenAI response must be an object")

    status = str(raw.get("status") or "completed")
    if status in {"failed", "cancelled", "incomplete"}:
        reason = _response_reason(raw)
        raise OpenAIHuntCaseError(
            f"OpenAI response status was {status}: {reason[:500]}"
        )

    parts = _output_text_parts(raw)
    if not parts:
        raise OpenAIHuntCaseError("OpenAI response had no output text")
    try:
        value = _decode_structured_object("".join(parts))
    except (json.JSONDecodeError, TypeError) as exc:
        raise OpenAIHuntCaseError(
            "OpenAI structured output was invalid JSON after joining all output segments"
        ) from exc

    usage = raw.get("usage") if isinstance(raw.get("usage"), Mapping) else {}
    return value, dict(usage)


def install_openai_hunt_case_schema_compat() -> None:
    """Install strict-schema and output-decoding compatibility patches."""
    from opportunity_engine.discovery import openai_hunt_case_enrichment

    triage_schema = strict_openai_schema(openai_hunt_case_enrichment.TriageOutput)
    deep_schema = strict_openai_schema(openai_hunt_case_enrichment.DeepOutput)
    _assert_strict_object_schema(triage_schema)
    _assert_strict_object_schema(deep_schema)
    openai_hunt_case_enrichment._schema = strict_openai_schema
    openai_hunt_case_enrichment.OpenAIResponsesHTTPClient.create_structured_response = (
        _compat_create_structured_response
    )
