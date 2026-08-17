from datetime import datetime
from zoneinfo import ZoneInfo

from opportunity_engine.discovery.sweden_psauction import (
    PSAUCTION_CLOTHING_QUERY_MATRIX,
    PSAUCTION_CURRENT_QUERY_IDS,
    build_psauction_clothing_queries,
)


def test_default_psauction_budget_prioritizes_current_window_then_inventory() -> None:
    now = datetime(2026, 8, 17, 12, 0, tzinfo=ZoneInfo("Europe/Stockholm"))
    queries = build_psauction_clothing_queries(8, now=now)

    assert [query.query_id for query in queries] == [
        "se-ps-current-01",
        "se-ps-current-02",
        "se-ps-05",
        "se-ps-08",
        "se-ps-09",
        "se-ps-14",
        "se-ps-11",
        "se-ps-12",
    ]
    assert len(queries) == 8
    assert {query.query_id for query in queries[:2]} == PSAUCTION_CURRENT_QUERY_IDS
    assert all("2026-08" in query.query for query in queries[:2])
    assert all("Auktionen avslutas" in query.query for query in queries[:2])
    assert any("konkursbo" in query.query for query in queries)
    assert any("restlager" in query.query for query in queries)


def test_status_marker_queries_remain_available_in_legacy_fallback_matrix() -> None:
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


def test_current_window_query_is_priority_hint_not_active_claim() -> None:
    now = datetime(2026, 8, 17, 12, 0, tzinfo=ZoneInfo("Europe/Stockholm"))
    current = build_psauction_clothing_queries(2, now=now)

    assert all(query.scenario == "AUCTION" for query in current)
    assert all(query.intent == "SALE_INTENT" for query in current)
    assert all(query.asset_scope == "CLOTHING_INVENTORY" for query in current)
