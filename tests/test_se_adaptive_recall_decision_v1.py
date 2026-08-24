from __future__ import annotations

import importlib.util
from pathlib import Path

from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.unified_search_truth_reconciliation_cli_hook import (
    reconcile_unified_search_truth,
)
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY, classify_project_domain
from opportunity_engine.search_experiment_execution_bridge_v1 import _market_anchored


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_exa_exact_lot_checkpoint.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_exa_exact_lot_checkpoint_se", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _strict_se_row() -> dict:
    url = "https://example.test/restpartier/1/20/parti/2359"
    return {
        "url": url,
        "final_url": url,
        "title": "Kläder restparti 2359",
        "query": "Sverige restpartier kläder grossist säljes parti",
        "exact_lot_origin": "MULTI_HOP",
        "evidence": {
            "project_domain": "CLOTHING_INVENTORY",
            "page_subject_domain": "CLOTHING_INVENTORY",
            "item_specific_url_evidence": True,
            "inventory_evidence": True,
            "direct_sale_evidence": True,
            "price_evidence": True,
            "quantity_evidence": True,
        },
    }


def test_sweden_has_one_source_neutral_zero_yield_recall_query() -> None:
    module = _load_runner()
    assert len(module.MARKET_ZERO_YIELD_RECALL_QUERIES["SE"]) == 1
    query = module.MARKET_ZERO_YIELD_RECALL_QUERIES["SE"][0]
    assert _market_anchored(query, "SE")
    assert classify_project_domain(text=query) == CLOTHING_INVENTORY
    assert "site:" not in query.casefold()
    assert "grossist.se" not in query.casefold()


def test_sweden_recall_runs_only_after_primary_zero(monkeypatch, tmp_path: Path) -> None:
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
                    title="Kläder grossist restparti",
                    url=f"https://example.test/search/{len(searches)}",
                    description="kläder restparti säljes",
                    provider="exa",
                )
            ][:count]

    def fake_verify(_benchmark, **_kwargs):
        return {"verified_pages": [], "exact_lot_candidate_count": 0}

    def fake_multihop(_verification, **_kwargs):
        nonlocal evaluations
        evaluations += 1
        if evaluations == 1:
            return {"exact_lots": [], "exact_lot_candidate_count": 0, "gateway_page_count": 0}
        return {
            "exact_lots": [_strict_se_row()],
            "exact_lot_candidate_count": 1,
            "gateway_page_count": 1,
        }

    monkeypatch.setattr(module, "ExaSearchProvider", FakeProvider)
    monkeypatch.setattr(module, "verify_provider_unique_pages", fake_verify)
    monkeypatch.setattr(module, "resolve_exact_lot_multihop", fake_multihop)

    result = module.run_market(
        market="SE",
        exa_api_key="test-key",
        output_dir=tmp_path,
        results_per_query=5,
    )

    assert searches[:3] == list(module.MARKET_EXACT_LOT_QUERY_PACKS["SE"])
    assert searches[3:] == list(module.MARKET_ZERO_YIELD_RECALL_QUERIES["SE"])
    report = result["search_run_report"]
    assert report["primary_strict_exact_lot_count"] == 0
    assert report["zero_yield_recall_triggered"] is True
    assert report["zero_yield_recall_added_exact_lot_count"] == 1
    assert report["strict_exact_lot_count"] == 1


def test_search_success_with_hits_and_zero_exact_is_not_discovery_failure() -> None:
    stages = [
        {"stage": "DISCOVERY", "status": "FAILURE", "source_execution_counts": {"FAILURE": 3}},
        {"stage": "EXACT_LOT_VERIFICATION", "status": "ADAPTED_FROM_CANONICAL_PIPELINE", "verified_active_exact_lot_count": 0},
        {"stage": "COMMERCIAL_QUALIFICATION", "status": "ADAPTED_FROM_CANONICAL_PIPELINE", "qualification_count": 0, "financial_decision_ready_count": 0},
        {"stage": "EVIDENCE", "status": "ADAPTED_FROM_CANONICAL_PIPELINE"},
        {"stage": "OPPORTUNITY_DECISION", "status": "BLOCKED_BY_DISCOVERY_FAILURE"},
    ]
    ledger = {
        "markets": [{"market_code": "SE", "stages": stages}],
        "search_runtime": {
            "CLOTHING_INVENTORY": {
                "markets": {
                    "SE": {"status": "SUCCESS", "hits_received": 15, "strict_exact_lot_count": 0}
                }
            }
        },
    }

    reconciled, _ = reconcile_unified_search_truth(ledger)
    final = {row["stage"]: row for row in reconciled["markets"][0]["stages"]}
    assert final["DISCOVERY"]["status"] == "PARTIAL"
    assert final["DISCOVERY"]["source_failures_preserved"] is True
    assert final["EXACT_LOT_VERIFICATION"]["status"] == "VALID_ZERO"
    assert final["COMMERCIAL_QUALIFICATION"]["status"] == "NOT_READY"
    assert final["EVIDENCE"]["status"] == "NOT_READY"
    assert final["OPPORTUNITY_DECISION"]["status"] == "NO_EXACT_LOT_CURRENTLY"
