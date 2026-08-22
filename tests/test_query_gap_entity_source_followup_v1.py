from __future__ import annotations

from opportunity_engine.discovery.search_provider import SearchHit


NEWS_URL = "https://www.nrk.no/nyheter/bauhaus-legger-ned-i-norge-1.17996380"
HOME_URL = "https://www.bauhaus.no/"
OFFICIAL_URL = "https://www.bauhaus.no/pressemelding-bauhaus-legger-ned-i-norge"

NEWS_HTML = """
<html><body>
<h1>Bauhaus legger ned i Norge</h1>
<p>Bauhaus legger ned alle butikker i Norge.</p>
<p>223 ansatte blir berørt av nedleggelsen.</p>
</body></html>
"""

OFFICIAL_HTML = """
<html><body>
<h1>BAUHAUS legger ned sin virksomhet i Norge</h1>
<p>BAUHAUS legger ned virksomheten i Norge.</p>
<p>Fra 22. august starter opphørssalg.</p>
<p>Alle varer skal ut, og hele lageret selges ut.</p>
</body></html>
"""


def _hit(url: str, title: str, description: str = "") -> SearchHit:
    return SearchHit(
        title=title,
        url=url,
        description=description,
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


def _checkpoint() -> dict:
    return {"deduplicated_opportunities": []}


def test_entity_source_followup_uses_company_without_leaking_learning_term() -> None:
    from opportunity_engine.query_gap_scout_waterfall import (
        SCOUT_QUERIES_NO,
        build_entity_source_followup_query,
        discover_query_gap_misses,
    )

    calls: list[str] = []

    def search(query: str):
        calls.append(query)
        if query == SCOUT_QUERIES_NO[0]:
            return [
                _hit(
                    NEWS_URL,
                    "Bauhaus legger ned i Norge",
                    "Bauhaus legger ned alle butikker i Norge.",
                )
            ]
        assert query == build_entity_source_followup_query("Bauhaus")
        return [
            _hit(
                OFFICIAL_URL,
                "BAUHAUS legger ned sin virksomhet i Norge",
                "Informasjon fra BAUHAUS Norge.",
            )
        ]

    def fetch_page(url: str):
        if url == NEWS_URL:
            return _page(url, NEWS_HTML)
        # This fixture intentionally makes the direct homepage probe fail,
        # proving the bounded Brave fallback still works afterward.
        if url == HOME_URL:
            raise OSError("probe unavailable")
        if url == OFFICIAL_URL:
            return _page(url, OFFICIAL_HTML)
        raise AssertionError(url)

    outcome = discover_query_gap_misses(
        _checkpoint(),
        active_queries=[],
        search=search,
        fetch_page=fetch_page,
        max_pages=3,
    )

    assert calls[0] == SCOUT_QUERIES_NO[0]
    assert calls[1] == build_entity_source_followup_query("Bauhaus")
    forbidden = {
        "sluttsalg",
        "avslutningssalg",
        "opphørssalg",
        "avviklingssalg",
        "tømmesalg",
    }
    assert not any(term in calls[1].casefold() for term in forbidden)

    assert outcome["search_request_count"] == 2
    assert outcome["page_request_count"] == 3
    assert outcome["entity_domain_probe_used"] is True
    assert outcome["entity_domain_probe_count"] == 1
    assert outcome["verified_page_count"] == 1
    assert outcome["detected_miss_count"] == 1
    assert outcome["waterfall_stopped_reason"] == "FIRST_VERIFIED_MISS"
    assert outcome["entity_source_followup_used"] is True
    assert outcome["entity_source_followup_company"] == "Bauhaus"
    assert outcome["search_stages"][1]["query_kind"] == "ENTITY_SOURCE_FOLLOW_UP"

    case = outcome["cases"][0]
    assert case.root_cause == "QUERY_GAP"
    assert case.ground_truth_company.casefold() == "bauhaus"
    assert case.ground_truth_url == OFFICIAL_URL
    assert outcome["cases_metadata"][0]["query_gap_term"] == "opphørssalg"
    assert outcome["cases_metadata"][0]["discovery_path"] == "ENTITY_SOURCE_FOLLOW_UP"
    assert outcome["automatic_query_activation"] is False


def test_entity_followup_falls_back_to_broad_query_without_closure_identity_cue() -> None:
    from opportunity_engine.query_gap_scout_waterfall import (
        SCOUT_QUERIES_NO,
        discover_query_gap_misses,
    )

    calls: list[str] = []
    noise_url = "https://example.no/ukjent-stenging"

    def search(query: str):
        calls.append(query)
        if query == SCOUT_QUERIES_NO[0]:
            return [_hit(noise_url, "Butikk stenger")]
        return []

    outcome = discover_query_gap_misses(
        _checkpoint(),
        active_queries=[],
        search=search,
        fetch_page=lambda url: _page(
            url,
            "<html><body><p>En butikk kan bli stengt senere.</p></body></html>",
        ),
    )

    assert calls == list(SCOUT_QUERIES_NO)
    assert outcome["entity_source_followup_used"] is False
    assert outcome["entity_source_followup_company"] is None
    assert outcome["entity_domain_probe_used"] is False
    assert outcome["search_stages"][1]["query_kind"] == "GENERIC_BROAD"
    assert outcome["detected_miss_count"] == 0


def test_entity_followup_does_not_relax_authoritative_page_verifier() -> None:
    from opportunity_engine.query_gap_scout_waterfall import (
        SCOUT_QUERIES_NO,
        build_entity_source_followup_query,
        discover_query_gap_misses,
    )

    calls: list[str] = []

    def search(query: str):
        calls.append(query)
        if query == SCOUT_QUERIES_NO[0]:
            return [_hit(NEWS_URL, "Bauhaus legger ned i Norge")]
        assert query == build_entity_source_followup_query("Bauhaus")
        return [_hit(OFFICIAL_URL, "BAUHAUS informasjon")]

    def fetch_page(url: str):
        if url == NEWS_URL:
            return _page(url, NEWS_HTML)
        if url == HOME_URL:
            raise OSError("probe unavailable")
        return _page(
            url,
            "<html><body><h1>BAUHAUS legger ned i Norge</h1><p>BAUHAUS legger ned.</p></body></html>",
        )

    outcome = discover_query_gap_misses(
        _checkpoint(),
        active_queries=[],
        search=search,
        fetch_page=fetch_page,
    )

    assert outcome["search_request_count"] == 2
    assert outcome["page_request_count"] == 3
    assert outcome["entity_domain_probe_used"] is True
    assert outcome["verified_page_count"] == 0
    assert outcome["detected_miss_count"] == 0
    assert outcome["verification_attempts"][-1]["verifier_status"] == "REJECTED"
    assert "SALE_TERM_MISSING" in outcome["verification_attempts"][-1]["rejection_reasons"]
    assert "INVENTORY_LIQUIDATION_MISSING" in outcome["verification_attempts"][-1]["rejection_reasons"]


def test_entity_followup_respects_existing_two_search_three_page_caps() -> None:
    from opportunity_engine.query_gap_scout_waterfall import (
        MAX_SEARCH_REQUESTS,
        SCOUT_QUERIES_NO,
        discover_query_gap_misses,
    )

    calls: list[str] = []
    official_noise_1 = "https://example.no/bauhaus-1"
    official_noise_2 = "https://example.no/bauhaus-2"
    official_noise_3 = "https://example.no/bauhaus-3"

    def search(query: str):
        calls.append(query)
        if query == SCOUT_QUERIES_NO[0]:
            return [_hit(NEWS_URL, "Bauhaus legger ned i Norge")]
        return [
            _hit(official_noise_1, "BAUHAUS info 1"),
            _hit(official_noise_2, "BAUHAUS info 2"),
            _hit(official_noise_3, "BAUHAUS info 3"),
        ]

    def fetch_page(url: str):
        if url == NEWS_URL:
            return _page(url, NEWS_HTML)
        if url == HOME_URL:
            raise OSError("probe unavailable")
        return _page(url, "<html><body>Ingen dokumentert lagertømming.</body></html>")

    outcome = discover_query_gap_misses(
        _checkpoint(),
        active_queries=[],
        search=search,
        fetch_page=fetch_page,
        max_pages=3,
    )

    assert MAX_SEARCH_REQUESTS == 2
    assert len(calls) == 2
    assert outcome["search_request_count"] == 2
    assert outcome["page_request_count"] == 3
    assert len(outcome["verification_attempts"]) == 3
    assert outcome["entity_domain_probe_used"] is True
    assert outcome["automatic_query_activation"] is False
