import json
from email.message import Message
from io import BytesIO
from urllib.error import HTTPError

import pytest

import opportunity_engine.cost_guard as cost_guard
import opportunity_engine.discovery.brave_search as brave_search
from opportunity_engine.discovery.search_provider import SearchHit


def _usage_limit_error() -> HTTPError:
    headers = Message()
    return HTTPError(
        url="https://api.search.brave.com/res/v1/web/search",
        code=402,
        msg="Payment Required",
        hdrs=headers,
        fp=BytesIO(
            json.dumps(
                {
                    "type": "ErrorResponse",
                    "error": {
                        "code": "USAGE_LIMIT_EXCEEDED",
                        "detail": "Monthly usage limit exceeded",
                    },
                }
            ).encode()
        ),
    )


def test_live_402_opens_process_circuit_and_skips_later_network_calls(monkeypatch):
    calls = {"count": 0}

    def capped_transport(request, timeout):
        calls["count"] += 1
        raise _usage_limit_error()

    # This test intentionally exercises the default transport. CI itself runs
    # under a GitHub push event, which is fail-closed by the paid-search guard,
    # so explicitly authorize only this simulated transport test.
    monkeypatch.setenv(cost_guard.PUSH_PAID_BRAVE_OVERRIDE, "true")
    brave_search._reset_usage_limit_circuit_for_tests()
    monkeypatch.setattr(brave_search, "_default_transport", capped_transport)
    try:
        first = brave_search.BraveSearchProvider("secret", max_retries=0)
        with pytest.raises(RuntimeError, match=r"HTTP 402.*USAGE_LIMIT_EXCEEDED"):
            first.search("clothing liquidation")

        second = brave_search.BraveSearchProvider("secret", max_retries=0)
        with pytest.raises(RuntimeError, match=r"usage limit circuit open after HTTP 402"):
            second.search("warehouse surplus clothing")

        assert calls["count"] == 1
    finally:
        brave_search._reset_usage_limit_circuit_for_tests()


def test_injected_test_transport_is_not_blocked_by_live_usage_limit_circuit():
    brave_search._reset_usage_limit_circuit_for_tests()
    brave_search._open_usage_limit_circuit()
    try:
        def injected_transport(request, timeout):
            return json.dumps(
                {
                    "web": {
                        "results": [
                            {
                                "title": "Commercial clothing stock lot",
                                "url": "https://example.com/lot",
                                "description": "Bulk inventory available",
                            }
                        ]
                    }
                }
            ).encode()

        provider = brave_search.BraveSearchProvider("secret", transport=injected_transport)
        assert provider.search("clothing stock") == [
            SearchHit(
                title="Commercial clothing stock lot",
                url="https://example.com/lot",
                description="Bulk inventory available",
                provider="Brave Search",
            )
        ]
    finally:
        brave_search._reset_usage_limit_circuit_for_tests()
