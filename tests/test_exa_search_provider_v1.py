from __future__ import annotations

import json
from urllib.error import HTTPError

import pytest

from opportunity_engine.discovery.exa_search import EXA_SEARCH_ENDPOINT, ExaSearchProvider


def test_exa_requires_api_key() -> None:
    with pytest.raises(ValueError, match="Exa API key is required"):
        ExaSearchProvider("   ")


def test_exa_search_posts_bounded_auto_search_and_normalizes_hits() -> None:
    captured = {}

    def transport(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["headers"] = {key.casefold(): value for key, value in request.header_items()}
        captured["body"] = json.loads((request.data or b"{}").decode("utf-8"))
        captured["timeout"] = timeout
        return json.dumps(
            {
                "requestId": "req-1",
                "results": [
                    {
                        "title": "Verified liquidation stock lot",
                        "url": "https://example.eu/lot/1",
                        "highlights": ["Business closure with remaining inventory for sale."],
                    },
                    {
                        "title": "Duplicate",
                        "url": "https://example.eu/lot/1",
                    },
                    {
                        "title": "Unsafe URL",
                        "url": "http://example.eu/not-https",
                    },
                ],
            }
        ).encode("utf-8")

    provider = ExaSearchProvider("exa-test-secret", transport=transport, timeout=7.5)
    hits = provider.search("  deadstock   liquidation Europe  ", count=5)

    assert captured["url"] == EXA_SEARCH_ENDPOINT
    assert captured["method"] == "POST"
    assert captured["headers"]["x-api-key"] == "exa-test-secret"
    assert captured["headers"]["content-type"] == "application/json"
    assert captured["body"] == {
        "query": "deadstock liquidation Europe",
        "numResults": 5,
        "type": "auto",
    }
    assert captured["timeout"] == 7.5
    assert len(hits) == 1
    assert hits[0].title == "Verified liquidation stock lot"
    assert hits[0].url == "https://example.eu/lot/1"
    assert hits[0].description == "Business closure with remaining inventory for sale."
    assert hits[0].provider == "Exa"


def test_exa_search_validates_query_and_count() -> None:
    provider = ExaSearchProvider("secret", transport=lambda request, timeout: b"{}")

    with pytest.raises(ValueError, match="search query must not be empty"):
        provider.search(" ")
    with pytest.raises(ValueError, match="count must be between 1 and 20"):
        provider.search("stock liquidation", count=0)
    with pytest.raises(ValueError, match="count must be between 1 and 20"):
        provider.search("stock liquidation", count=21)


def test_exa_provider_error_never_exposes_api_key() -> None:
    secret = "exa-super-secret-value"

    def transport(request, timeout):
        raise HTTPError(request.full_url, 401, "Unauthorized", hdrs=None, fp=None)

    provider = ExaSearchProvider(secret, transport=transport, max_retries=0)
    with pytest.raises(RuntimeError) as exc_info:
        provider.search("liquidation")

    message = str(exc_info.value)
    assert "HTTP 401" in message
    assert secret not in message
