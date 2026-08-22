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
<h1>BAUHAUS Norge</h1>
<a href="/bauhaus-norge-informasjon">BAUHAUS Norge Informasjon</a>
</body></html>
"""
INFO_HTML = """
<html><body>
<h1>BAUHAUS legger ned sin virksomhet i Norge</h1>
<p>BAUHAUS legger ned virksomheten i Norge.</p>
<p>Fra 22. august starter opphørssalg.</p>
<p>Alle varer skal ut, og hele lageret selges ut.</p>
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


def test_domain_probe_candidate_is_conservative_and_contains_no_learning_term() -> None:
    from opportunity_engine.query_gap_scout_waterfall import (
        build_entity_first_party_probe_urls,
    )

    assert build_entity_first_party_probe_urls("Bauhaus") == [HOME_URL]
    assert build_entity_first_party_probe_urls("Bauhaus Norge AS") == [HOME_URL]

    joined = " ".join(build_entity_first_party_probe_urls("Bauhaus")).casefold()
    forbidden = {
        "sluttsalg",
        "avslutningssalg",
        "opphørssalg",
        "avviklingssalg",
        "tømmesalg",
    }
    assert not any(term in joined for term in forbidden)


def test_direct_domain_probe_can_reach_verified_internal_source_before_second_search() -> None:
    from opportunity_engine.query_gap_scout_waterfall import (
        SCOUT_QUERIES_NO,
        discover_query_gap_misses,
    )

    search_calls: list[str] = []
    fetched: list[str] = []

    def search(query: str):
        search_calls.append(query)
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

    assert search_calls == [SCOUT_QUERIES_NO[0]]
    assert fetched == [NEWS_URL, HOME_URL, INFO_URL]
    assert outcome["search_request_count"] == 1
    assert outcome["page_request_count"] == 3
    assert outcome["entity_domain_probe_used"] is True
    assert outcome["entity_domain_probe_count"] == 1
    assert outcome["entity_internal_followup_used"] is True
    assert outcome["entity_internal_followup_count"] == 1
    assert outcome["verified_page_count"] == 1
    assert outcome["detected_miss_count"] == 1
    assert outcome["waterfall_stopped_reason"] == "FIRST_VERIFIED_MISS"
    assert outcome["cases_metadata"][0]["query_gap_term"] == "opphørssalg"
    assert outcome["cases_metadata"][0]["discovery_path"] == "ENTITY_INTERNAL_SOURCE_FOLLOW_UP"
    assert outcome["automatic_query_activation"] is False
