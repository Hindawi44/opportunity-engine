from __future__ import annotations

from opportunity_engine.discovery.search_provider import SearchHit


NRK_URL = (
    "https://www.nrk.no/nyheter/"
    "bauhaus-legger-ned-i-norge_-_-223-personer-pavirkes-av-nedleggelsen-1.17996380"
)
OFFICIAL_URL = "https://www.bauhaus.no/bauhaus-norge-informasjon"

NRK_HTML = """
<html><body>
<h1>Bauhaus legger ned i Norge</h1>
<p>Bauhaus legger ned alle butikker i Norge.</p>
<p>Alle tre varehus i Norge legges ned.</p>
</body></html>
"""

OFFICIAL_HTML = """
<html><body>
<h1>BAUHAUS Norge Informasjon</h1>
<p>BAUHAUS avvikler virksomheten i Norge.</p>
<p>Opphørssalget starter lørdag 22. august.</p>
<p>I forbindelse med avviklingen vil vi selge ut vårt sortiment.</p>
<p>Lagerstatusen er kun en indikasjon på tilgjengelig lagerbeholdning.</p>
</body></html>
"""


def _hit(url: str, title: str, description: str) -> SearchHit:
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


def _restricted_queries() -> list[str]:
    return [
        "opphørssalg arbeidsklær sikkerhetssko Norge",
        '("opphørssalg" OR "avviklingssalg") (klær OR klesbutikk OR tekstil)',
        "lagersalg arbeidsklær vernesko Norge",
    ]


def test_scope_state_and_root_cause_distinguish_absent_restricted_and_broad() -> None:
    from opportunity_engine.query_gap_scout_waterfall import (
        query_term_root_cause,
        query_term_scope_state,
    )

    assert query_term_scope_state("sluttsalg", _restricted_queries()) == "ABSENT"
    assert query_term_root_cause("sluttsalg", _restricted_queries()) == "QUERY_GAP"

    assert query_term_scope_state("opphørssalg", _restricted_queries()) == "VERTICAL_RESTRICTED"
    assert query_term_root_cause("opphørssalg", _restricted_queries()) == "QUERY_SCOPE_GAP"

    broad = [*_restricted_queries(), "opphørssalg varelager sortiment Norge"]
    assert query_term_scope_state("opphørssalg", broad) == "BROAD"
    assert query_term_root_cause("opphørssalg", broad) is None


def test_entity_follow_up_query_does_not_leak_gap_terms() -> None:
    from opportunity_engine.query_gap_scout_waterfall import build_entity_follow_up_query

    query = build_entity_follow_up_query("Bauhaus")
    folded = query.casefold()

    assert '"bauhaus"' in folded
    assert any(term in folded for term in ("varer", "varelager", "lagerbeholdning", "sortiment"))
    for forbidden in (
        "opphørssalg",
        "avslutningssalg",
        "avviklingssalg",
        "tømmesalg",
        "sluttsalg",
    ):
        assert forbidden not in folded


def test_official_bauhaus_page_is_verified_without_relaxing_stock_gate() -> None:
    from opportunity_engine.query_gap_page_verifier_v2 import verify_query_gap_page_v2
    from opportunity_engine.query_gap_scout_waterfall import diagnose_public_page

    diagnostic = diagnose_public_page(_page(OFFICIAL_URL, OFFICIAL_HTML))
    proof = verify_query_gap_page_v2(_page(OFFICIAL_URL, OFFICIAL_HTML))

    assert diagnostic["verifier_status"] == "VERIFIED"
    assert diagnostic["company"] == "BAUHAUS"
    assert diagnostic["evidence_flags"]["closure_marker"] is True
    assert diagnostic["evidence_flags"]["sale_term"] is True
    assert diagnostic["evidence_flags"]["liquidation_marker"] is True
    assert proof is not None
    assert proof["company"] == "BAUHAUS"
    assert "opphørssalg" in proof["query_gap_terms"]


def test_partial_closure_entity_routes_second_request_to_entity_follow_up() -> None:
    from opportunity_engine.query_gap_scout_waterfall import (
        SCOUT_QUERIES_NO,
        build_entity_follow_up_query,
        discover_query_gap_misses,
    )

    calls: list[str] = []

    def search(query: str):
        calls.append(query)
        if query == SCOUT_QUERIES_NO[0]:
            return [
                _hit(
                    NRK_URL,
                    "Bauhaus legger ned i Norge",
                    "Bauhaus legger ned alle butikker i Norge.",
                )
            ]
        if query == build_entity_follow_up_query("Bauhaus"):
            return [
                _hit(
                    OFFICIAL_URL,
                    "BAUHAUS Norge Informasjon",
                    "Informasjon om avvikling av virksomheten i Norge.",
                )
            ]
        return []

    def fetch(url: str):
        return _page(url, NRK_HTML if url == NRK_URL else OFFICIAL_HTML)

    outcome = discover_query_gap_misses(
        {"deduplicated_opportunities": []},
        active_queries=_restricted_queries(),
        search=search,
        fetch_page=fetch,
        max_pages=3,
    )

    assert calls == [SCOUT_QUERIES_NO[0], build_entity_follow_up_query("Bauhaus")]
    assert outcome["search_request_count"] == 2
    assert outcome["page_request_count"] == 2
    assert outcome["verified_page_count"] == 1
    assert outcome["detected_miss_count"] == 1
    assert outcome["entity_follow_up_used"] is True
    assert outcome["entity_follow_up_company"].casefold() == "bauhaus"

    [case] = outcome["cases"]
    assert case.ground_truth_company == "BAUHAUS"
    assert case.ground_truth_url == OFFICIAL_URL
    assert case.root_cause == "QUERY_SCOPE_GAP"
    assert case.trace.query_generated is True
    assert case.learning_status == "DIAGNOSED"

    [metadata] = outcome["cases_metadata"]
    assert metadata["query_gap_term"] == "opphørssalg"
    assert metadata["query_scope_state"] == "VERTICAL_RESTRICTED"
    assert metadata["root_cause"] == "QUERY_SCOPE_GAP"
    assert outcome["automatic_query_activation"] is False


def test_absent_term_still_creates_plain_query_gap() -> None:
    from opportunity_engine.query_gap_scout_waterfall import discover_query_gap_misses

    outcome = discover_query_gap_misses(
        {"deduplicated_opportunities": []},
        active_queries=[],
        search=lambda query: [
            _hit(OFFICIAL_URL, "BAUHAUS Norge Informasjon", "Avvikling i Norge")
        ],
        fetch_page=lambda url: _page(url, OFFICIAL_HTML),
        max_pages=1,
    )

    [case] = outcome["cases"]
    assert case.root_cause == "QUERY_GAP"
    assert case.trace.query_generated is False


def test_broad_existing_query_does_not_mislabel_scope_gap() -> None:
    from opportunity_engine.query_gap_scout_waterfall import discover_query_gap_misses

    outcome = discover_query_gap_misses(
        {"deduplicated_opportunities": []},
        active_queries=["opphørssalg varelager sortiment Norge"],
        search=lambda query: [
            _hit(OFFICIAL_URL, "BAUHAUS Norge Informasjon", "Avvikling i Norge")
        ],
        fetch_page=lambda url: _page(url, OFFICIAL_HTML),
        max_pages=1,
    )

    assert outcome["detected_miss_count"] == 0
    assert outcome["broad_query_already_covered_count"] == 1
    assert outcome["automatic_query_activation"] is False
