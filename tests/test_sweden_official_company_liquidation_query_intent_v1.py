from __future__ import annotations

import opportunity_engine.discovery.commercial_anchor_query_expansion as anchors
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY


def test_sweden_official_company_query_targets_liquidation_inventory(monkeypatch) -> None:
    monkeypatch.setattr(
        anchors,
        "load_sweden_official_company_anchors",
        lambda **_: (
            ("OFFICIAL_COMPANY", "Seventy8 AB"),
            ("OFFICIAL_COMPANY", "H Branding AB"),
        ),
    )

    rows = anchors.build_commercial_anchor_queries(
        market="SE",
        project_domain=CLOTHING_INVENTORY,
        max_queries=anchors.MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET,
    )

    assert len(rows) == 2
    assert [row["anchor_value"] for row in rows] == ["Seventy8 AB", "H Branding AB"]
    for row in rows:
        query = row["query"].casefold()
        assert f'"{row["anchor_value"].casefold()}"' in query
        assert "konkursbo" in query
        assert "likvidation" in query
        assert "varulager" in query
        assert "konkursauktion" in query
        assert "grossist" not in query
        assert row["anchor_is_qualification_evidence"] is False
        assert row["source_specific"] is False


def test_sweden_generic_catalog_keeps_existing_wholesale_query(monkeypatch) -> None:
    monkeypatch.setattr(anchors, "load_sweden_official_company_anchors", lambda **_: ())

    row = anchors.build_commercial_anchor_queries(
        market="SE",
        project_domain=CLOTHING_INVENTORY,
        max_queries=1,
    )[0]

    query = row["query"].casefold()
    assert row["anchor_type"] == "BRAND"
    assert row["anchor_value"] == "Jack & Jones"
    assert "restparti" in query
    assert "grossist" in query
    assert "konkursbo" not in query
    assert "konkursauktion" not in query
