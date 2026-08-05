"""OpenAI strict Structured Outputs compatibility for hunt-case schemas.

Pydantic fields with defaults are optional in its generated JSON Schema, while
OpenAI strict Structured Outputs require every property to be listed in
``required`` and every object to reject additional properties. This module
normalizes only the hunt-case schema generator; it does not change model
validation or any opportunity lifecycle decision.
"""
from __future__ import annotations

from typing import Any, Mapping

from pydantic import BaseModel


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


def install_openai_hunt_case_schema_compat() -> None:
    """Install the narrow schema normalizer on the hunt-case module."""
    from opportunity_engine.discovery import openai_hunt_case_enrichment

    openai_hunt_case_enrichment._schema = strict_openai_schema
