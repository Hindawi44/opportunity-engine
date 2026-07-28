import pytest

from opportunity_engine.discovery.brave_precision import (
    BRAVE_PRECISION_FRESHNESS,
    build_clothing_inventory_precision_queries,
)
from opportunity_engine.discovery.clothing_inventory_search import (
    CLOTHING_INVENTORY_QUERY_MATRIX,
    DiscoveryQuery,
)


def test_precision_policy_preserves_the_approved_query_matrix_contract():
    precision = build_clothing_inventory_precision_queries()

    assert BRAVE_PRECISION_FRESHNESS == "pm"
    assert len(precision) == 16
    assert [item.query_id for item in precision] == [
        item.query_id for item in CLOTHING_INVENTORY_QUERY_MATRIX
    ]
    for base, refined in zip(CLOTHING_INVENTORY_QUERY_MATRIX, precision, strict=True):
        assert refined.query_id == base.query_id
        assert refined.scenario == base.scenario
        assert refined.intent == base.intent
        assert refined.asset_scope == base.asset_scope
        assert refined.rotation_group == base.rotation_group
        assert refined.query != base.query


def test_direct_sale_queries_exclude_buyer_intent_and_predictable_noise():
    by_id = {
        query.query_id: query.query
        for query in build_clothing_inventory_precision_queries()
    }

    buyer_exclusion_ids = {
        "sale-01",
        "sale-02",
        "sale-03",
        "sale-04",
        "sale-06",
        "special-01",
        "special-02",
        "special-03",
    }
    for query_id in buyer_exclusion_ids:
        assert '-"ønskes kjøpt"' in by_id[query_id]
        assert "-kjøpes" in by_id[query_id]

    for query_id, text in by_id.items():
        assert "-" in text, query_id


def test_event_queries_keep_event_recall_but_remove_jobs_and_generic_content():
    queries = build_clothing_inventory_precision_queries()
    event_queries = [query for query in queries if query.intent == "EVENT_LEAD"]

    assert len(event_queries) == 6
    for query in event_queries:
        assert "-jobb" in query.query
        assert "-stilling" in query.query
        assert "-nettbutikk" in query.query
        assert "-wikipedia" in query.query
        assert "-podcast" in query.query


def test_precision_policy_fails_closed_when_the_base_matrix_changes():
    changed = (*CLOTHING_INVENTORY_QUERY_MATRIX, DiscoveryQuery(
        "unexpected",
        "AUCTION",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        "unexpected query",
    ))

    with pytest.raises(ValueError, match="does not match the approved query matrix"):
        build_clothing_inventory_precision_queries(changed)
