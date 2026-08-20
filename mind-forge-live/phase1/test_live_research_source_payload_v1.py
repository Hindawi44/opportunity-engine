from __future__ import annotations

from dataclasses import dataclass

from mind_forge.live_research_adapter_v1 import (
    _as_jsonish,
    _count_web_search_calls,
    _extract_sources,
)


@dataclass
class _Source:
    url: str
    title: str


@dataclass
class _Action:
    sources: list[_Source]


@dataclass
class _WebSearchCall:
    type: str
    action: _Action


@dataclass
class _ModelResponse:
    output: list[object]


def test_agents_sdk_dataclass_payload_exposes_web_search_sources():
    response = _ModelResponse(
        output=[
            _WebSearchCall(
                type="web_search_call",
                action=_Action(
                    sources=[
                        _Source(
                            url="https://example.test/source",
                            title="Example Source",
                        )
                    ]
                ),
            )
        ]
    )

    payload = _as_jsonish(response)

    assert _count_web_search_calls([payload]) == 1
    assert _extract_sources([payload]) == {
        "https://example.test/source": "Example Source"
    }
