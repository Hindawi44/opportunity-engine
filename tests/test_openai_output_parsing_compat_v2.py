from __future__ import annotations

from typing import Any

import pytest

from opportunity_engine.discovery.openai_hunt_case_enrichment import (
    OpenAIHuntCaseError,
    OpenAIResponsesHTTPClient,
)


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeSession:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.kwargs: dict[str, Any] | None = None

    def post(self, *args: Any, **kwargs: Any) -> FakeResponse:
        self.kwargs = kwargs
        return FakeResponse(self.payload)


def _call(
    payload: dict[str, Any],
    *,
    schema_name: str = "market_hunt_case_triage",
    max_output_tokens: int = 100,
) -> tuple[dict[str, Any], dict[str, Any], FakeSession]:
    session = FakeSession(payload)
    client = OpenAIResponsesHTTPClient(api_key="test-key", session=session)
    value, usage = client.create_structured_response(
        model="gpt-5.6-luna",
        instructions="Return strict JSON.",
        input_text="{}",
        schema_name=schema_name,
        schema={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        reasoning_effort="medium",
        max_output_tokens=max_output_tokens,
    )
    return value, usage, session


def test_joins_all_output_text_segments_before_json_decode() -> None:
    payload = {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": '{"cases":[],'},
                    {"type": "output_text", "text": '"unassigned_signal_ids":[]}'},
                ],
            }
        ],
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    }

    value, usage, _ = _call(payload)

    assert value == {"cases": [], "unassigned_signal_ids": []}
    assert usage["total_tokens"] == 15


def test_decodes_fenced_json_output() -> None:
    payload = {
        "status": "completed",
        "output_text": "```json\n{\"cases\":[],\"unassigned_signal_ids\":[]}\n```",
        "usage": {},
    }

    value, _, _ = _call(payload)

    assert value["cases"] == []


def test_decodes_json_encoded_object_string() -> None:
    payload = {
        "status": "completed",
        "output_text": '"{\\"cases\\":[],\\"unassigned_signal_ids\\":[]}"',
        "usage": {},
    }

    value, _, _ = _call(payload)

    assert value == {"cases": [], "unassigned_signal_ids": []}


def test_incomplete_response_reports_precise_reason() -> None:
    payload = {
        "status": "incomplete",
        "incomplete_details": {"reason": "max_output_tokens"},
        "output": [],
        "usage": {"input_tokens": 100, "output_tokens": 2400, "total_tokens": 2500},
    }

    with pytest.raises(OpenAIHuntCaseError) as exc_info:
        _call(payload)

    message = str(exc_info.value)
    assert "incomplete" in message
    assert "max_output_tokens" in message


def test_triage_uses_no_reasoning_and_larger_output_budget() -> None:
    payload = {
        "status": "completed",
        "output_text": '{"cases":[],"unassigned_signal_ids":[]}',
        "usage": {},
    }

    _, _, session = _call(payload, max_output_tokens=1200)

    assert session.kwargs is not None
    request = session.kwargs["json"]
    assert request["reasoning"] == {"effort": "none"}
    assert request["max_output_tokens"] >= 2400
    assert request["store"] is False
    assert request["text"]["format"]["strict"] is True


def test_deep_analysis_uses_low_reasoning_and_larger_output_budget() -> None:
    payload = {
        "status": "completed",
        "output_text": "{}",
        "usage": {},
    }

    _, _, session = _call(
        payload,
        schema_name="market_hunt_case_deep_analysis",
        max_output_tokens=1400,
    )

    assert session.kwargs is not None
    request = session.kwargs["json"]
    assert request["reasoning"] == {"effort": "low"}
    assert request["max_output_tokens"] >= 1800


def test_invalid_joined_json_remains_a_controlled_failure() -> None:
    payload = {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": '{"cases":['},
                ],
            }
        ],
        "usage": {},
    }

    with pytest.raises(OpenAIHuntCaseError) as exc_info:
        _call(payload)

    assert "invalid JSON" in str(exc_info.value)
