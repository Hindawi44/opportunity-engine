import json

import pytest

from opportunity_engine.ods.brave_search import BraveSearchClient, parse_brave_results


def test_client_builds_authorized_bounded_request_without_exposing_key():
    captured = {}

    def transport(url, timeout, headers):
        captured["url"] = url
        captured["headers"] = headers
        return json.dumps({"web": {"results": []}}).encode("utf-8")

    client = BraveSearchClient(api_key="secret-value", transport=transport)
    assert client.search("butikkinnredning", count=5) == []
    assert "q=butikkinnredning" in captured["url"]
    assert "count=5" in captured["url"]
    assert "secret-value" not in captured["url"]
    assert captured["headers"]["X-Subscription-Token"] == "secret-value"


def test_parse_results_preserves_only_direct_fields():
    payload = {
        "web": {
            "results": [
                {
                    "title": "Butikkinnredning selges",
                    "url": "https://example.no/ad/1",
                    "description": "Komplett inventar",
                    "page_age": "2026-07-22T08:00:00Z",
                },
                {"title": "Missing URL"},
            ]
        }
    }
    assert parse_brave_results(json.dumps(payload)) == [
        {
            "title": "Butikkinnredning selges",
            "url": "https://example.no/ad/1",
            "snippet": "Komplett inventar",
            "source": "Brave Search",
            "published_at": "2026-07-22T08:00:00Z",
        }
    ]


def test_invalid_configuration_and_payload_are_rejected():
    with pytest.raises(ValueError):
        BraveSearchClient(api_key="")
    with pytest.raises(ValueError):
        BraveSearchClient(api_key="x").search("", count=1)
    with pytest.raises(ValueError):
        BraveSearchClient(api_key="x").search("query", count=21)
    with pytest.raises(RuntimeError):
        parse_brave_results("not-json")
