from __future__ import annotations

from opportunity_engine.discovery.search_provider import SearchHit


NEWS_URL = "https://www.nrk.no/nyheter/bauhaus-legger-ned-i-norge-1.17996380"
HOME_URL = "https://www.bauhaus.no/"
INFO_URL = "https://www.bauhaus.no/bauhaus-norge-informasjon"

NEWS_HTML = """
<html><body>
<h1>Bauhaus legger ned i Norge</h1>
<p>Bauhaus legger ned alle butikker i Norge.</p>
</body></html>
"""

HOME_HTML = """
<html><body>
<h1>BAUHAUS</h1>
<a href="/maling-tapet/produkt">Produkt</a>
<a href="https://example.com/informasjon">Ekstern informasjon</a>
<a href="/bauhaus-norge-informasjon">Se mer informasjon her</a>
</body></html>
"""

INFO_HTML = """
<html><body>
<h1>BAUHAUS legger ned virksomheten i Norge</h1>
<p>BAUHAUS avvikles i Norge.</p>
<p>Opphørssalg starter 22. august.</p>
<p>Lagerbeholdningen skal selges ut før butikkene stenger.</p>
</body></html>
"""


def _hit(url: str, title: str) -> SearchHit:
    return SearchHit(
        title=title,
        url=url,
        description="",
        provider="Brave Search",
    )


def _page(url: str, html: str):
    from opportunity_engine.automatic_query_gap_miss_scout import PublicPage

    return PublicPage(
        requested_url=url,
        final_url=url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        html=html,
    )


def test_extract_internal_source_links_keeps_same_domain_information_links_only() -> None:
    from opportunity_engine.query_gap_scout_waterfall import (
        extract_entity_internal_source_links,
    )

    links = extract_entity_internal_source_links(
        _page(HOME_URL, HOME_HTML),
        company="Bauhaus",
    )

    assert links == [INFO_URL]


def test_official_homepage_can_follow_one_internal_page_to_verified_query_gap() -> None:
    from opportunity_engine.query_gap_scout_waterfall import (
        SCOUT_QUERIES_NO,
        discover_query_gap_misses,
    )

    calls: list[str] = []
    fetched: list[str] = []

    def search(query: str):
        calls.append(query)
        assert query == SCOUT_QUERIES_NO[0]
        return [_hit(NEWS_URL, "Bauhaus legger ned i Norge")]

    def fetch_page(url: str):
        fetched.append(url)
        if url == NEWS_URL:
            return _page(url, NEWS_HTML)
        if url == HOME_URL:
            return _page(url, HOME_HTML)
        if url == INFO_URL:
            return _page(url, INFO_HTML)
        raise AssertionError(url)

    outcome = discover_query_gap_misses(
        {"deduplicated_opportunities": []},
        active_queries=[],
        search=search,
        fetch_page=fetch_page,
        max_pages=3,
    )

    # V10 probes the plausible first-party homepage before spending Brave #2.
    assert calls == [SCOUT_QUERIES_NO[0]]
    assert fetched == [NEWS_URL, HOME_URL, INFO_URL]
    assert outcome["search_request_count"] == 1
    assert outcome["page_request_count"] == 3
    assert outcome["verified_page_count"] == 1
    assert outcome["detected_miss_count"] == 1
    assert outcome["waterfall_stopped_reason"] == "FIRST_VERIFIED_MISS"
    # No entity Brave search was needed because the direct domain probe succeeded.
    assert outcome["entity_source_followup_used"] is False
    assert outcome["entity_domain_probe_used"] is True
    assert outcome["entity_domain_probe_count"] == 1
    assert outcome["entity_internal_followup_used"] is True
    assert outcome["entity_internal_followup_count"] == 1
    assert outcome["verification_attempts"][-1]["query_kind"] == "ENTITY_INTERNAL_SOURCE_FOLLOW_UP"
    assert outcome["cases_metadata"][0]["discovery_path"] == "ENTITY_INTERNAL_SOURCE_FOLLOW_UP"
    assert outcome["cases_metadata"][0]["query_gap_term"] == "opphørssalg"
    assert outcome["automatic_query_activation"] is False
