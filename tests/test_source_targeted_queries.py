import pytest

from opportunity_engine.discovery.clothing_inventory_search import (
    CLOTHING_INVENTORY_QUERY_MATRIX,
    DiscoveryQuery,
)
from opportunity_engine.discovery.source_targeted_queries import (
    SOURCE_TARGETED_FRESHNESS,
    SOURCE_TARGETED_QUERY_BUDGET,
    SOURCE_TARGETED_REFERENCE_QUERIES,
    build_source_targeted_queries,
    select_source_targeted_queries,
)


def test_source_targeted_policy_preserves_the_canonical_query_contract():
    targeted = build_source_targeted_queries()

    assert SOURCE_TARGETED_FRESHNESS == "pm"
    assert SOURCE_TARGETED_QUERY_BUDGET == 8
    assert len(targeted) == 16
    assert [query.query_id for query in targeted] == [
        query.query_id for query in CLOTHING_INVENTORY_QUERY_MATRIX
    ]
    for base, refined in zip(CLOTHING_INVENTORY_QUERY_MATRIX, targeted, strict=True):
        assert refined.query_id == base.query_id
        assert refined.scenario == base.scenario
        assert refined.intent == base.intent
        assert refined.asset_scope == base.asset_scope
        assert refined.rotation_group == base.rotation_group
        assert refined.query.count("site:") == 1
        assert refined.query != base.query


def test_default_budget_covers_all_approved_source_families():
    selected = select_source_targeted_queries()
    text = "\n".join(query.query for query in selected)

    assert len(selected) == 8
    assert "site:auksjonen.no" in text
    assert "site:norskavvikling.no" in text
    assert "site:stadssalg.no" in text
    assert "site:finn.no/recommerce/forsale/item" in text
    assert "site:forvalt.no/Konkurs" in text
    assert "site:virksomhet.brreg.no" in text
    assert "site:konkurs.app" in text


def test_query_budget_fails_closed():
    with pytest.raises(ValueError, match="query_budget"):
        select_source_targeted_queries(0)
    with pytest.raises(ValueError, match="query_budget"):
        select_source_targeted_queries(17)


def test_reference_queries_are_bounded_and_traceable():
    assert [query.query_id for query in SOURCE_TARGETED_REFERENCE_QUERIES] == [
        "reference-axl",
        "reference-by-fiona",
        "reference-tommeliten",
    ]
    assert all(query.rotation_group == "SECONDARY" for query in SOURCE_TARGETED_REFERENCE_QUERIES)
    assert all(query.query.count("site:") == 1 for query in SOURCE_TARGETED_REFERENCE_QUERIES)


def test_source_targeted_policy_fails_when_the_base_matrix_changes():
    changed = (*CLOTHING_INVENTORY_QUERY_MATRIX, DiscoveryQuery(
        "unexpected",
        "AUCTION",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        "unexpected",
    ))

    with pytest.raises(ValueError, match="does not match the approved query matrix"):
        build_source_targeted_queries(changed)
