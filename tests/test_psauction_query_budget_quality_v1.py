from opportunity_engine.discovery.sweden_psauction import (
    PSAUCTION_CLOTHING_QUERY_MATRIX,
    build_psauction_clothing_queries,
)


def test_default_psauction_budget_prioritizes_inventory_queries() -> None:
    queries = build_psauction_clothing_queries(8)

    assert [query.query_id for query in queries] == [
        "se-ps-05",
        "se-ps-08",
        "se-ps-09",
        "se-ps-14",
        "se-ps-11",
        "se-ps-12",
        "se-ps-15",
        "se-ps-06",
    ]
    assert any("konkursbo" in query.query for query in queries)
    assert any("restlager" in query.query for query in queries)
    assert all("Auktionen avslutas" not in query.query for query in queries)


def test_status_marker_queries_remain_available_beyond_daily_budget() -> None:
    default_ids = {query.query_id for query in build_psauction_clothing_queries(8)}
    status_queries = [
        query
        for query in PSAUCTION_CLOTHING_QUERY_MATRIX
        if "Auktionen avslutas" in query.query
    ]

    assert {query.query_id for query in status_queries} == {
        "se-ps-01",
        "se-ps-02",
        "se-ps-03",
        "se-ps-04",
    }
    assert all(query.query_id not in default_ids for query in status_queries)
