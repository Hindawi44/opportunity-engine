from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

from opportunity_engine.discovery.brave_search import BraveSearchProvider


def _payload() -> bytes:
    return json.dumps({"web": {"results": []}}).encode("utf-8")


def test_exact_psauction_status_lookup_ignores_configured_freshness():
    seen_urls: list[str] = []

    def transport(request, timeout):
        seen_urls.append(request.full_url)
        return _payload()

    provider = BraveSearchProvider(
        "test-key",
        transport=transport,
        freshness="pm",
        country="SE",
        operators=True,
    )

    provider.search('site:psauction.se/item/view "826330"', count=5)

    params = parse_qs(urlparse(seen_urls[0]).query)
    assert params["q"] == ['site:psauction.se/item/view "826330"']
    assert "freshness" not in params


def test_normal_discovery_query_keeps_configured_freshness():
    seen_urls: list[str] = []

    def transport(request, timeout):
        seen_urls.append(request.full_url)
        return _payload()

    provider = BraveSearchProvider(
        "test-key",
        transport=transport,
        freshness="pm",
        country="SE",
        operators=True,
    )

    provider.search('site:psauction.se kläder konkurs lager', count=5)

    params = parse_qs(urlparse(seen_urls[0]).query)
    assert params["freshness"] == ["pm"]


def test_other_exact_site_lookup_does_not_lose_freshness():
    seen_urls: list[str] = []

    def transport(request, timeout):
        seen_urls.append(request.full_url)
        return _payload()

    provider = BraveSearchProvider(
        "test-key",
        transport=transport,
        freshness="pm",
        country="SE",
        operators=True,
    )

    provider.search('site:example.com/item "826330"', count=5)

    params = parse_qs(urlparse(seen_urls[0]).query)
    assert params["freshness"] == ["pm"]
