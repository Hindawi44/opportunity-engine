from __future__ import annotations

from opportunity_engine.discovery.search_provider import SearchHit


def _hit(url: str, title: str) -> SearchHit:
    return SearchHit(
        title=title,
        url=url,
        description="",
        provider="Brave Search",
    )


def test_entity_query_biases_toward_first_party_information_pages_without_sale_terms() -> None:
    from opportunity_engine.query_gap_scout_waterfall import (
        build_entity_source_followup_query,
    )

    query = build_entity_source_followup_query("Bauhaus").casefold()

    assert "avvikler" in query or "avvikles" in query
    assert "sortiment" in query
    assert "informasjon" in query
    assert "pressemelding" in query
    assert "kundeservice" in query

    forbidden = {
        "sluttsalg",
        "avslutningssalg",
        "opphørssalg",
        "avviklingssalg",
        "tømmesalg",
    }
    assert not any(term in query for term in forbidden)


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
