from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.automatic_query_gap_miss_scout import (
    PublicPage,
    discover_query_gap_misses,
)
from opportunity_engine.discovery.search_provider import SearchHit


NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


def _checkpoint() -> dict:
    return {"deduplicated_opportunities": []}


def test_query_gap_scout_rejects_verified_bauhaus_closure_as_out_of_domain() -> None:
    hit = SearchHit(
        title="BAUHAUS Norge avvikler virksomheten",
        url="https://www.bauhaus.no/avvikling",
        description="Avviklingssalg. Hele lagerbeholdningen skal ut.",
        provider="Fake Brave",
    )

    def page(url: str) -> PublicPage:
        return PublicPage(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            html=(
                "<html><body><h1>BAUHAUS Norge avvikler virksomheten</h1>"
                "<p>Vi avvikler virksomheten og har avviklingssalg. Hele lagerbeholdningen "
                "med byggematerialer, verktøy, fliser og trelast skal ut.</p></body></html>"
            ),
        )

    report = discover_query_gap_misses(
        _checkpoint(),
        active_queries=[],
        search=lambda query: [hit],
        fetch_page=page,
        observed_at=NOW,
        max_pages=1,
    )

    assert report["detected_miss_count"] == 0
    assert report["out_of_domain_verified_page_count"] == 1
    assert report["cases"] == []


def test_query_gap_scout_keeps_verified_clothing_closure() -> None:
    hit = SearchHit(
        title="Senze of Joy avviklingssalg",
        url="https://example.no/senze-avvikling",
        description="Klesbutikk stenger. Hele varelageret av klær selges ut.",
        provider="Fake Brave",
    )

    def page(url: str) -> PublicPage:
        return PublicPage(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            html=(
                "<html><body><h1>Senze of Joy stenger butikken</h1>"
                "<p>Vi avvikler virksomheten og har avviklingssalg. Hele varelageret "
                "av klær, jakker og bukser skal ut.</p></body></html>"
            ),
        )

    report = discover_query_gap_misses(
        _checkpoint(),
        active_queries=[],
        search=lambda query: [hit],
        fetch_page=page,
        observed_at=NOW,
        max_pages=1,
    )

    assert report["detected_miss_count"] == 1
    assert report["out_of_domain_verified_page_count"] == 0
    assert report["cases"][0].opportunity_type == "VERIFIED_STORE_CLOSURE_INVENTORY_LIQUIDATION"
