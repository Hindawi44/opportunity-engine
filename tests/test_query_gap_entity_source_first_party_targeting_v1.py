from __future__ import annotations

from opportunity_engine.discovery.search_provider import SearchHit


def _hit(url: str, title: str) -> SearchHit:
    return SearchHit(
        title=title,
        url=url,
        description="",
        provider="Brave Search",
    )


def test_entity_query_is_minimal_navigation_without_sale_terms() -> None:
    from opportunity_engine.query_gap_scout_waterfall import (
        build_entity_source_followup_query,
    )

    query = build_entity_source_followup_query("Bauhaus")
    folded = query.casefold()

    assert query == '"Bauhaus" Norge'
    assert "offisiell" not in folded
    assert "nettside" not in folded
    assert "hjemmeside" not in folded
    assert "kundeservice" not in folded
    assert "informasjon" not in folded
    assert "legger ned" not in folded
    assert "avvikler" not in folded
    assert "sortiment" not in folded

    forbidden = {
        "sluttsalg",
        "avslutningssalg",
        "opphørssalg",
        "avviklingssalg",
        "tømmesalg",
    }
    assert not any(term in folded for term in forbidden)


def test_entity_source_hits_prioritize_company_domain_and_information_path() -> None:
    from opportunity_engine.query_gap_scout_waterfall import (
        prioritize_entity_source_hits,
    )

    news = _hit(
        "https://www.nettavisen.no/okonomi/bauhaus-legger-ned/s/5-95-1",
        "Bauhaus legger ned driften i Norge",
    )
    generic_first_party = _hit(
        "https://www.bauhaus.no/maling-tapet/produkt",
        "Produkt | BAUHAUS",
    )
    official_info = _hit(
        "https://www.bauhaus.no/bauhaus-norge-informasjon",
        "BAUHAUS Norge Informasjon",
    )

    ranked = prioritize_entity_source_hits(
        [news, generic_first_party, official_info],
        company="Bauhaus",
    )

    assert [item.url for item in ranked] == [
        official_info.url,
        generic_first_party.url,
        news.url,
    ]
