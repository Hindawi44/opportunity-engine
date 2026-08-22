from __future__ import annotations


def test_entity_source_followup_discovers_official_site_without_event_or_sale_term_leak() -> None:
    """Live V7 proved topical entity queries still rank news ahead of first-party pages."""
    from opportunity_engine.query_gap_scout_waterfall import (
        build_entity_source_followup_query,
    )

    query = build_entity_source_followup_query("Bauhaus").casefold()

    assert "offisiell" in query
    assert "nettside" in query
    assert "hjemmeside" in query
    assert "norge" in query

    # Stage 2 is source discovery, not another topical closure search.
    assert "legger ned" not in query
    assert "avvikler" not in query
    assert "sortiment" not in query
    assert "varelager" not in query

    forbidden = {
        "sluttsalg",
        "avslutningssalg",
        "opphørssalg",
        "avviklingssalg",
        "tømmesalg",
    }
    assert not any(term in query for term in forbidden)
