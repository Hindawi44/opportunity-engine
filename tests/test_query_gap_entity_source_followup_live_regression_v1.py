from __future__ import annotations


def test_entity_source_followup_is_minimal_navigational_query_without_event_or_sale_leak() -> None:
    """Live V8 proved source-intent words still biased Brave toward news coverage.

    Stage 2 should now be a pure navigational lookup for the entity's Norwegian
    web presence. Ranking and exact-page verification, not query wording, must
    decide whether a returned URL is useful first-party evidence.
    """
    from opportunity_engine.query_gap_scout_waterfall import (
        build_entity_source_followup_query,
    )

    query = build_entity_source_followup_query("Bauhaus")
    folded = query.casefold()

    assert query == '"Bauhaus" Norge'

    # Stage 2 is entity navigation only, not another topical search.
    forbidden_navigation_bias = {
        "offisiell",
        "nettside",
        "hjemmeside",
        "kundeservice",
        "informasjon",
        "pressemelding",
        "legger ned",
        "avvikler",
        "sortiment",
        "varelager",
    }
    assert not any(term in folded for term in forbidden_navigation_bias)

    # Learned sale language remains withheld from every scout query.
    forbidden_learning_terms = {
        "sluttsalg",
        "avslutningssalg",
        "opphørssalg",
        "avviklingssalg",
        "tømmesalg",
    }
    assert not any(term in folded for term in forbidden_learning_terms)
