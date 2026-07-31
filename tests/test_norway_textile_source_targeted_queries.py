from opportunity_engine.discovery.norway_textile_keywords import (
    NORWAY_TEXTILE_CATEGORIES,
    NORWAY_TEXTILE_QUERY_IDS,
)
from opportunity_engine.discovery.norway_textile_source_targeted_queries import (
    build_norway_textile_source_targeted_queries,
    select_norway_textile_source_targeted_queries,
)


def test_source_targeted_adapter_preserves_keyword_pack_contract() -> None:
    queries = build_norway_textile_source_targeted_queries()

    assert tuple(query.query_id for query in queries) == NORWAY_TEXTILE_QUERY_IDS
    assert {query.asset_scope for query in queries} == NORWAY_TEXTILE_CATEGORIES
    assert len(queries) == 16
    assert all("site:" in query.query for query in queries)
    assert all("Norge" not in query.query for query in queries)


def test_source_targeted_adapter_covers_expanded_textile_scope() -> None:
    by_id = {
        query.query_id: query
        for query in build_norway_textile_source_targeted_queries()
    }

    assert by_id["sale-02"].asset_scope == "FABRIC_TEXTILE_STOCK"
    assert by_id["sale-03"].asset_scope == "SEWING_MACHINERY"
    assert by_id["sale-05"].asset_scope == "TAILOR_WORKSHOP_LIQUIDATION"
    assert by_id["lead-02"].asset_scope == "SEWING_ATELIER_LIQUIDATION"
    assert by_id["lead-03"].asset_scope == "SEWING_FACTORY_LIQUIDATION"
    assert by_id["special-04"].asset_scope == "CLOTHING_STORE_FIXTURES"


def test_source_targeted_selector_is_bounded_and_priority_ordered() -> None:
    selected = select_norway_textile_source_targeted_queries(4)

    assert [query.query_id for query in selected] == [
        "sale-03",
        "sale-05",
        "sale-02",
        "sale-04",
    ]


def test_source_targeted_selector_rejects_invalid_budget() -> None:
    for budget in (0, 17):
        try:
            select_norway_textile_source_targeted_queries(budget)
        except ValueError as exc:
            assert "query_budget must be between 1 and 16" in str(exc)
        else:
            raise AssertionError("invalid query budget must fail closed")
