from __future__ import annotations

from opportunity_engine.discovery.search_provider import SearchHit


NEW_TERM = "nedleggelsessalg"
URL = "https://example.no/nytt-nedleggelsessalg"
HTML = """
<html><body>
<h1>Nordlys Mote legger ned</h1>
<p>Klesbutikken Nordlys Mote i Tromsø stenger for godt.</p>
<p>Nå starter Nedleggelsessalget.</p>
<p>Hele varelageret skal selges ut, og alle varer skal ut av butikken.</p>
<p>Siste åpningsdag er 30. september.</p>
</body></html>
"""

SEASONAL_ONLY_HTML = """
<html><body>
<h1>Nordlys Mote legger ned</h1>
<p>Klesbutikken Nordlys Mote i Tromsø stenger for godt.</p>
<p>Vi har også vårt vanlige Sommersalg denne uken.</p>
<p>Hele varelageret skal selges ut, og alle varer skal ut av butikken.</p>
</body></html>
"""


def _page(html: str):
    from opportunity_engine.automatic_query_gap_miss_scout import PublicPage

    return PublicPage(
        requested_url=URL,
        final_url=URL,
        status_code=200,
        content_type="text/html; charset=utf-8",
        html=html,
    )


def _hit() -> SearchHit:
    return SearchHit(
        title="Nordlys Mote legger ned",
        url=URL,
        description="Butikken stenger for godt og selger ut hele varelageret.",
        provider="Brave Search",
    )


def test_verified_closure_can_discover_sale_term_not_present_in_static_gap_list() -> None:
    from opportunity_engine.query_gap_scout_waterfall import discover_query_gap_misses

    outcome = discover_query_gap_misses(
        {"deduplicated_opportunities": []},
        active_queries=['("opphørssalg" OR "avviklingssalg") butikk'],
        search=lambda query: [_hit()],
        fetch_page=lambda url: _page(HTML),
    )

    assert outcome["verified_page_count"] == 1
    assert outcome["detected_miss_count"] == 1
    [case] = outcome["cases"]
    assert case.root_cause == "QUERY_GAP"
    assert case.ground_truth_company == "Nordlys Mote"
    assert case.diagnosed_query_gap_terms == (NEW_TERM,)
    assert NEW_TERM in case.learning_evidence_text.casefold()
    assert outcome["cases_metadata"][0]["query_gap_term"] == NEW_TERM
    assert outcome["cases_metadata"][0]["source_page_verified"] is True
    assert all(NEW_TERM not in query.casefold() for query in outcome["executed_queries"])
    assert outcome["automatic_query_activation"] is False
    assert outcome["automatic_contact"] is False
    assert outcome["automatic_bid"] is False
    assert outcome["automatic_purchase"] is False
    assert outcome["automatic_payment"] is False


def test_seasonal_sale_word_does_not_become_query_gap_language() -> None:
    from opportunity_engine.query_gap_scout_waterfall import discover_query_gap_misses

    outcome = discover_query_gap_misses(
        {"deduplicated_opportunities": []},
        active_queries=[],
        search=lambda query: [_hit()],
        fetch_page=lambda url: _page(SEASONAL_ONLY_HTML),
    )

    assert outcome["detected_miss_count"] == 0
    assert outcome["verified_page_count"] == 0
    assert outcome["automatic_query_activation"] is False
