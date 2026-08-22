from __future__ import annotations

from opportunity_engine.discovery.search_provider import SearchHit


RITA_URL = (
    "https://www.vartoslo.no/anbefalt-bydel-sentrum-hille-melbye-arkitekter/"
    "butikken-legger-ned-etter-90-ar-store-planer-for-sentrumsbygarden/1252479"
)
RITA_HTML = """
<html><body>
<h1>Butikken legger ned etter 90 år</h1>
<p>Klesbutikken Rita Korsettsalong i Storgata 9 stenger etter 90 år.</p>
<p>I vinduet står det «Sluttsalg» og «Alt skal ut».</p>
<p>Rita Korsettsalong legges ned. Alle varer skal ut av butikken.</p>
<p>Siste åpningsdag blir 1. oktober.</p>
</body></html>
"""


def _hit(url: str, title: str = "Butikken legger ned") -> SearchHit:
    return SearchHit(
        title=title,
        url=url,
        description="Butikken stenger for godt.",
        provider="Brave Search",
    )


def _checkpoint() -> dict:
    return {"deduplicated_opportunities": []}


def _page(url: str, html: str):
    from opportunity_engine.automatic_query_gap_miss_scout import PublicPage

    return PublicPage(
        requested_url=url,
        final_url=url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        html=html,
    )


def test_waterfall_queries_are_distinct_and_do_not_leak_learning_terms() -> None:
    from opportunity_engine.query_gap_scout_waterfall import (
        MAX_SEARCH_REQUESTS,
        SCOUT_QUERIES_NO,
    )

    forbidden = {
        "sluttsalg",
        "avslutningssalg",
        "opphørssalg",
        "avviklingssalg",
        "tømmesalg",
    }
    assert MAX_SEARCH_REQUESTS == 2
    assert len(SCOUT_QUERIES_NO) == 2
    assert len(set(SCOUT_QUERIES_NO)) == 2
    for query in SCOUT_QUERIES_NO:
        folded = query.casefold()
        assert not any(term in folded for term in forbidden)


def test_waterfall_uses_second_query_when_first_path_has_no_hits() -> None:
    from opportunity_engine.query_gap_scout_waterfall import (
        SCOUT_QUERIES_NO,
        discover_query_gap_misses,
    )

    calls: list[str] = []

    def search(query: str):
        calls.append(query)
        if query == SCOUT_QUERIES_NO[0]:
            return []
        return [_hit(RITA_URL)]

    outcome = discover_query_gap_misses(
        _checkpoint(),
        active_queries=[],
        search=search,
        fetch_page=lambda url: _page(url, RITA_HTML),
    )

    assert calls == list(SCOUT_QUERIES_NO)
    assert outcome["search_request_count"] == 2
    assert outcome["detected_miss_count"] == 1
    assert outcome["page_request_count"] == 1
    assert outcome["waterfall_enabled"] is True
    assert [stage["hit_count"] for stage in outcome["search_stages"]] == [0, 1]


def test_waterfall_stops_after_first_verified_miss_to_save_cost() -> None:
    from opportunity_engine.query_gap_scout_waterfall import (
        SCOUT_QUERIES_NO,
        discover_query_gap_misses,
    )

    calls: list[str] = []

    def search(query: str):
        calls.append(query)
        return [_hit(RITA_URL)]

    outcome = discover_query_gap_misses(
        _checkpoint(),
        active_queries=[],
        search=search,
        fetch_page=lambda url: _page(url, RITA_HTML),
    )

    assert calls == [SCOUT_QUERIES_NO[0]]
    assert outcome["search_request_count"] == 1
    assert outcome["detected_miss_count"] == 1
    assert len(outcome["search_stages"]) == 1


def test_waterfall_reserves_recall_for_fallback_and_shares_global_page_budget() -> None:
    from opportunity_engine.query_gap_scout_waterfall import (
        SCOUT_QUERIES_NO,
        discover_query_gap_misses,
    )

    noise_url = "https://example.no/closure-story"
    fetched: list[str] = []

    def search(query: str):
        if query == SCOUT_QUERIES_NO[0]:
            return [_hit(noise_url), _hit("https://example.no/second-strict-hit")]
        return [_hit(noise_url), _hit(RITA_URL), _hit("https://example.no/fallback-noise")]

    def fetch_page(url: str):
        fetched.append(url)
        if url == RITA_URL:
            return _page(url, RITA_HTML)
        return _page(
            url,
            "<html><body><p>Butikken stenger for godt, men ingen lageravvikling er dokumentert.</p></body></html>",
        )

    outcome = discover_query_gap_misses(
        _checkpoint(),
        active_queries=[],
        search=search,
        fetch_page=fetch_page,
        max_pages=2,
    )

    # The strict stage may spend only the first page before fallback gets a turn.
    assert fetched == [noise_url, RITA_URL]
    assert outcome["search_request_count"] == 2
    assert outcome["page_request_count"] == 2
    assert outcome["detected_miss_count"] == 1
    assert outcome["search_stages"][0]["page_request_count"] == 1
    assert outcome["search_stages"][1]["page_request_count"] == 1


def test_waterfall_deduplicates_urls_across_search_stages() -> None:
    from opportunity_engine.query_gap_scout_waterfall import (
        SCOUT_QUERIES_NO,
        discover_query_gap_misses,
    )

    duplicate = "https://example.no/same-result"
    fetched: list[str] = []

    def search(query: str):
        if query == SCOUT_QUERIES_NO[0]:
            return [_hit(duplicate)]
        return [_hit(duplicate), _hit(RITA_URL)]

    def fetch_page(url: str):
        fetched.append(url)
        if url == RITA_URL:
            return _page(url, RITA_HTML)
        return _page(url, "<html><body>Butikken stenger for godt.</body></html>")

    outcome = discover_query_gap_misses(
        _checkpoint(),
        active_queries=[],
        search=search,
        fetch_page=fetch_page,
        max_pages=3,
    )

    assert fetched.count(duplicate) == 1
    assert fetched.count(RITA_URL) == 1
    assert outcome["detected_miss_count"] == 1
    assert outcome["search_request_count"] == 2
