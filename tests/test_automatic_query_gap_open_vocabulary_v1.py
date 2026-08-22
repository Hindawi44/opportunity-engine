from __future__ import annotations

from opportunity_engine.discovery.search_provider import SearchHit


NEW_TERM = "nedleggelsessalg"
URL = "https://example.no/nytt-nedleggelsessalg"
HTML = """
<html><body>
<h1>Nordlys Mote legger ned</h1>
<p>Klesbutikken Nordlys Mote i Tromsø stenger for godt.</p>
<p>Nå starter vårt store Nedleggelsessalg.</p>
<p>Hele varelageret skal selges ut, og alle varer skal ut av butikken.</p>
<p>Siste åpningsdag er 30. september.</p>
</body></html>
"""


def test_verified_closure_can_discover_sale_term_not_present_in_static_gap_list() -> None:
    from opportunity_engine.automatic_query_gap_miss_scout import (
        PublicPage,
        discover_query_gap_misses,
    )

    hit = SearchHit(
        title="Nordlys Mote legger ned",
        url=URL,
        description="Butikken stenger for godt og selger ut hele varelageret.",
        provider="Brave Search",
    )

    outcome = discover_query_gap_misses(
        {"deduplicated_opportunities": []},
        active_queries=['("opphørssalg" OR "avviklingssalg") butikk'],
        search=lambda query: [hit],
        fetch_page=lambda url: PublicPage(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            html=HTML,
        ),
    )

    assert outcome["verified_page_count"] == 1
    assert outcome["detected_miss_count"] == 1
    [case] = outcome["cases"]
    assert case.root_cause == "QUERY_GAP"
    assert case.ground_truth_company == "Nordlys Mote"
    assert NEW_TERM in case.learning_evidence_text.casefold()
    assert outcome["cases_metadata"][0]["query_gap_term"] == NEW_TERM
    assert outcome["cases_metadata"][0]["source_page_verified"] is True
    assert outcome["automatic_query_activation"] is False
    assert outcome["automatic_contact"] is False
    assert outcome["automatic_bid"] is False
    assert outcome["automatic_purchase"] is False
    assert outcome["automatic_payment"] is False
