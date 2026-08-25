from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from opportunity_engine.discovery.commercial_anchor_query_expansion import (
    MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET,
    build_commercial_anchor_queries,
)
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    FABRIC_PROCUREMENT,
    classify_project_domain,
)
from opportunity_engine.search_experiment_execution_bridge_v1 import _market_anchored


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_exa_exact_lot_checkpoint.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_exa_exact_lot_checkpoint_anchor", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _strict_row(url: str, query: str) -> dict:
    return {
        "url": url,
        "final_url": url,
        "title": "Wholesale clothing exact lot",
        "query": query,
        "exact_lot_origin": "MULTI_HOP",
        "evidence": {
            "project_domain": CLOTHING_INVENTORY,
            "page_subject_domain": CLOTHING_INVENTORY,
            "item_specific_url_evidence": True,
            "inventory_evidence": True,
            "direct_sale_evidence": True,
            "price_evidence": True,
            "quantity_evidence": True,
        },
    }


def test_anchor_queries_are_bounded_market_anchored_and_domain_safe() -> None:
    for market in ("NO", "SE", "DE", "FR", "IT", "NL"):
        rows = build_commercial_anchor_queries(
            market=market,
            project_domain=CLOTHING_INVENTORY,
        )
        assert 1 <= len(rows) <= MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET
        for row in rows:
            query = row["query"]
            assert _market_anchored(query, market)
            assert classify_project_domain(text=query) == CLOTHING_INVENTORY
            assert row["anchor_is_qualification_evidence"] is False
            assert row["source_specific"] is False
            assert "site:" not in query.casefold()


def test_same_contract_can_build_fabric_anchor_query_without_creating_new_domain() -> None:
    rows = build_commercial_anchor_queries(
        market="NL",
        project_domain=FABRIC_PROCUREMENT,
    )
    assert rows
    assert rows[0]["project_domain"] == FABRIC_PROCUREMENT
    assert classify_project_domain(text=rows[0]["query"]) == FABRIC_PROCUREMENT
    assert rows[0]["anchor_is_qualification_evidence"] is False


def test_brand_name_alone_never_rescues_failed_exact_lot_evidence() -> None:
    module = _load_runner()
    row = _strict_row(
        "https://example.test/product/pronovias",
        "France vêtements Pronovias déstockage stock lot à vendre",
    )
    row["evidence"]["page_subject_domain"] = "OUT_OF_DOMAIN"
    assert module._exact_lot_rows({"verified_pages": []}, {"exact_lots": [row]}) == []


def test_anchor_stage_runs_only_for_thin_post_recall_yield(monkeypatch, tmp_path: Path) -> None:
    module = _load_runner()
    searches: list[str] = []
    evaluations = 0

    class FakeProvider:
        def __init__(self, _key: str):
            pass

        def search(self, query: str, *, count: int):
            searches.append(query)
            return [
                SearchHit(
                    title="Wholesale clothing stock",
                    url=f"https://example.test/search/{len(searches)}",
                    description="clothing stock wholesale",
                    provider="exa",
                )
            ][:count]

    def fake_verify(_benchmark, **_kwargs):
        return {"verified_pages": [], "exact_lot_candidate_count": 0}

    def fake_multihop(_verification, **_kwargs):
        nonlocal evaluations
        evaluations += 1
        if evaluations == 1:
            rows = []
        elif evaluations == 2:
            rows = [
                _strict_row("https://example.test/product/100-kleding", module.MARKET_ZERO_YIELD_RECALL_QUERIES["NL"][0]),
                _strict_row("https://example.test/product/200-kleding", module.MARKET_ZERO_YIELD_RECALL_QUERIES["NL"][0]),
            ]
        else:
            anchor_query = build_commercial_anchor_queries(
                market="NL", project_domain=CLOTHING_INVENTORY
            )[0]["query"]
            rows = [
                _strict_row("https://example.test/product/100-kleding", module.MARKET_ZERO_YIELD_RECALL_QUERIES["NL"][0]),
                _strict_row("https://example.test/product/200-kleding", module.MARKET_ZERO_YIELD_RECALL_QUERIES["NL"][0]),
                _strict_row("https://example.test/product/300-kleding", anchor_query),
            ]
        return {
            "exact_lots": rows,
            "exact_lot_candidate_count": len(rows),
            "gateway_page_count": 1,
        }

    monkeypatch.setattr(module, "ExaSearchProvider", FakeProvider)
    monkeypatch.setattr(module, "verify_provider_unique_pages", fake_verify)
    monkeypatch.setattr(module, "resolve_exact_lot_multihop", fake_multihop)

    result = module.run_market(
        market="NL",
        exa_api_key="test-key",
        output_dir=tmp_path,
        results_per_query=5,
    )

    anchor_rows = build_commercial_anchor_queries(
        market="NL", project_domain=CLOTHING_INVENTORY
    )
    assert searches == [
        module.MARKET_EXACT_LOT_QUERY_PACKS["NL"][0],
        module.MARKET_ZERO_YIELD_RECALL_QUERIES["NL"][0],
        *(row["query"] for row in anchor_rows),
    ]
    report = result["search_run_report"]
    assert report["primary_strict_exact_lot_count"] == 0
    assert report["zero_yield_recall_added_exact_lot_count"] == 2
    assert report["commercial_anchor_expansion_triggered"] is True
    assert report["commercial_anchor_query_count"] == len(anchor_rows)
    assert report["commercial_anchor_pre_strict_exact_lot_count"] == 2
    assert report["commercial_anchor_added_exact_lot_count"] == 1
    assert report["commercial_anchor_is_qualification_evidence"] is False
    assert report["strict_exact_lot_count"] == 3

    resolution = json.loads((tmp_path / "exa-exact-lot-resolution.json").read_text())
    assert [row["query_stage"] for row in resolution["queries"]] == [
        "PRIMARY",
        "ZERO_YIELD_RECALL",
        "COMMERCIAL_ANCHOR",
        "COMMERCIAL_ANCHOR",
    ]
    anchor_meta = [
        row["commercial_anchor"]
        for row in resolution["queries"]
        if row["query_stage"] == "COMMERCIAL_ANCHOR"
    ]
    assert all(row["qualification_evidence"] is False for row in anchor_meta)


def test_anchor_stage_is_not_spent_on_strong_primary_yield(monkeypatch, tmp_path: Path) -> None:
    module = _load_runner()
    searches: list[str] = []

    class FakeProvider:
        def __init__(self, _key: str):
            pass

        def search(self, query: str, *, count: int):
            searches.append(query)
            return [
                SearchHit(
                    title="Wholesale clothing stock",
                    url=f"https://example.test/search/{len(searches)}",
                    description="clothing stock wholesale",
                    provider="exa",
                )
            ][:count]

    def fake_verify(_benchmark, **_kwargs):
        return {"verified_pages": [], "exact_lot_candidate_count": 0}

    def fake_multihop(_verification, **_kwargs):
        query = module.MARKET_EXACT_LOT_QUERY_PACKS["FR"][0]
        rows = [
            _strict_row(f"https://example.test/product/{n}-vetements", query)
            for n in range(1, 4)
        ]
        return {
            "exact_lots": rows,
            "exact_lot_candidate_count": len(rows),
            "gateway_page_count": 1,
        }

    monkeypatch.setattr(module, "ExaSearchProvider", FakeProvider)
    monkeypatch.setattr(module, "verify_provider_unique_pages", fake_verify)
    monkeypatch.setattr(module, "resolve_exact_lot_multihop", fake_multihop)

    result = module.run_market(
        market="FR",
        exa_api_key="test-key",
        output_dir=tmp_path,
        results_per_query=5,
    )

    assert searches == list(module.MARKET_EXACT_LOT_QUERY_PACKS["FR"])
    report = result["search_run_report"]
    assert report["primary_strict_exact_lot_count"] == 3
    assert report["commercial_anchor_expansion_triggered"] is False
    assert report["commercial_anchor_query_count"] == 0
    assert report["strict_exact_lot_count"] == 3
