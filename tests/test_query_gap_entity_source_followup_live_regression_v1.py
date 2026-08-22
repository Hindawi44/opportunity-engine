from __future__ import annotations


def test_entity_source_followup_covers_avvikling_language_without_sale_term_leak() -> None:
    """Live proof V5 found BAUHAUS but the follow-up query repeated the NRK hit.

    BAUHAUS's official source describes the closure as avvikling, so entity-source
    recall must cover that closure vocabulary while still withholding all terms
    that the learner is supposed to discover from the verified page itself.
    """
    from opportunity_engine.query_gap_scout_waterfall import (
        build_entity_source_followup_query,
    )

    query = build_entity_source_followup_query("Bauhaus").casefold()

    assert "avvikler" in query or "avvikles" in query
    assert "sortiment" in query

    forbidden = {
        "sluttsalg",
        "avslutningssalg",
        "opphørssalg",
        "avviklingssalg",
        "tømmesalg",
    }
    assert not any(term in query for term in forbidden)
