from __future__ import annotations

from opportunity_engine.discovery.commercial_anchor_query_expansion import (
    MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET,
    build_commercial_anchor_queries,
)
from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    FABRIC_PROCUREMENT,
    classify_project_domain,
)
from opportunity_engine.search_experiment_execution_bridge_v1 import _market_anchored


def test_germany_uses_live_proven_wholesaler_anchor_without_source_pinning() -> None:
    rows = build_commercial_anchor_queries(
        market="DE",
        project_domain=CLOTHING_INVENTORY,
    )

    assert len(rows) == MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET == 2
    assert [row["anchor_value"] for row in rows] == [
        "Salzmann Restwaren",
        "Jack & Jones",
    ]
    assert [row["anchor_type"] for row in rows] == ["WHOLESALER", "BRAND"]
    assert all(row["anchor_origin"] == "EVIDENCE_BACKED_MARKET_ENTITY_V1" for row in rows)

    for row in rows:
        query = row["query"]
        assert _market_anchored(query, "DE")
        assert classify_project_domain(text=query) == CLOTHING_INVENTORY
        assert row["anchor_is_qualification_evidence"] is False
        assert row["source_specific"] is False
        assert "site:" not in query.casefold()
        assert ".de" not in query.casefold()
        assert "http" not in query.casefold()


def test_german_override_does_not_leak_to_other_clothing_markets() -> None:
    rows = build_commercial_anchor_queries(
        market="NL",
        project_domain=CLOTHING_INVENTORY,
    )

    assert [row["anchor_value"] for row in rows] == ["Jack & Jones", "Pronovias"]
    assert all(row["anchor_origin"] == "CONTROLLED_GLOBAL_CATALOG_V1" for row in rows)


def test_german_clothing_override_does_not_change_fabric_anchor_contract() -> None:
    rows = build_commercial_anchor_queries(
        market="DE",
        project_domain=FABRIC_PROCUREMENT,
    )

    assert len(rows) == 1
    assert rows[0]["anchor_value"] == "Wouters Textiles"
    assert rows[0]["anchor_type"] == "WHOLESALER"
    assert rows[0]["anchor_origin"] == "CONTROLLED_GLOBAL_CATALOG_V1"
    assert rows[0]["anchor_is_qualification_evidence"] is False
    assert classify_project_domain(text=rows[0]["query"]) == FABRIC_PROCUREMENT
