import json
from email.message import Message
from io import BytesIO
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

import pytest

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.live_search import run_live_discovery
from opportunity_engine.discovery.search_provider import SearchHit


NOW = "2026-07-24T16:00:00+00:00"


def test_brave_provider_builds_norway_request_and_normalizes_hits():
    captured = {}

    def transport(request, timeout):
        captured["url"] = request.full_url
        captured["token"] = request.get_header("X-subscription-token")
        captured["timeout"] = timeout
        return json.dumps({
            "web": {"results": [
                {
                    "title": "Komplett varelager klær selges",
                    "url": "https://example.no/lot-1",
                    "description": "Hele lageret fra klesbutikk til salgs",
                },
                {
                    "title": "Duplicate",
                    "url": "https://example.no/lot-1",
                    "description": "same URL",
                },
                {"title": "Unsafe", "url": "http://example.no/unsafe"},
            ]}
        }).encode()

    provider = BraveSearchProvider("secret", transport=transport)
    hits = provider.search("  varelager   klær  ", count=5)

    params = parse_qs(urlparse(captured["url"]).query)
    assert params["q"] == ["varelager klær"]
    assert params["country"] == ["NO"]
    assert "search_lang" not in params
    assert "ui_lang" not in params
    assert params["result_filter"] == ["web"]
    assert params["count"] == ["5"]
    assert captured["token"] == "secret"
    assert captured["timeout"] == 20.0
    assert hits == [SearchHit(
        title="Komplett varelager klær selges",
        url="https://example.no/lot-1",
        description="Hele lageret fra klesbutikk til salgs",
        provider="Brave Search",
    )]


def test_brave_provider_exposes_safe_http_error_body():
    headers = Message()
    error = HTTPError(
        url="https://api.search.brave.com/res/v1/web/search",
        code=422,
        msg="Unprocessable Entity",
        hdrs=headers,
        fp=BytesIO(b'{"message":"Invalid search_lang"}'),
    )

    def transport(request, timeout):
        raise error

    provider = BraveSearchProvider("secret", transport=transport, max_retries=0)
    with pytest.raises(RuntimeError, match=r"HTTP 422.*Invalid search_lang"):
        provider.search("varelager klær")


@pytest.mark.parametrize("count", [0, 21])
def test_brave_provider_rejects_invalid_count(count):
    provider = BraveSearchProvider("secret", transport=lambda request, timeout: b"{}")
    with pytest.raises(ValueError):
        provider.search("varelager klær", count=count)


class FakeProvider:
    name = "Fake Search"

    def search(self, query, *, count=10):
        if query == "failed query":
            raise RuntimeError("temporary provider failure")
        return [
            SearchHit(
                "Komplett varelager klær selges",
                "https://example.no/confirmed",
                "Hele lageret fra butikk til salgs",
                self.name,
            ),
            SearchHit(
                "Klesbutikk konkurs",
                "https://example.no/lead",
                "Konkursbo for klesbutikk",
                self.name,
            ),
            SearchHit(
                "Brukt jakke",
                "https://example.no/single",
                "En jakke selges privat",
                self.name,
            ),
            SearchHit(
                "Duplicate confirmed",
                "https://example.no/confirmed",
                "duplicate URL",
                self.name,
            ),
        ]


def test_live_discovery_classifies_deduplicates_and_hands_off_confirmed_sales_only():
    report = run_live_discovery(
        ["varelager klær", "varelager klær", "failed query"],
        FakeProvider(),
        discovered_at=NOW,
        results_per_query=10,
        query_delay_seconds=0,
    )

    assert report["queries_submitted"] == 2
    assert report["hits_received"] == 4
    assert report["candidates_received"] == 3
    assert report["duplicates_removed"] == 1
    assert report["confirmed_sales"] == 1
    assert report["follow_up_leads"] == 1
    assert report["rejected_results"] == 1
    assert len(report["canonical_opportunities"]) == 1
    assert report["canonical_opportunities"][0]["source"]["url"] == "https://example.no/confirmed"
    assert report["canonical_opportunities"][0]["source"]["asking_price_nok"] is None
    assert report["automatic_purchase_decision"] is False
    assert report["status"] == "PARTIAL"
    assert report["errors"] == [{"query": "failed query", "error": "temporary provider failure"}]
