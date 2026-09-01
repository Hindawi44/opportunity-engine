from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from opportunity_engine.discovery.checkpoint_state_restore import DATABASE_RELATIVE_PATHS
from opportunity_engine.discovery.exa_exact_lot_shadow_hunt import MARKET_EXACT_LOT_QUERIES
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.source_artifact_continuity import _time
from opportunity_engine.discovery.unified_opportunity_report import build_unified_opportunity_report
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY, classify_project_domain
from opportunity_engine.search_policy_query_challenge_v1 import (
    CHALLENGES,
    POLICY_CHALLENGE_STAGE,
)
from opportunity_engine.search_experiment_execution_bridge_v1 import _market_anchored


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_exa_exact_lot_checkpoint.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_exa_exact_lot_checkpoint", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _strict_row(url: str = "https://example.test/product/500-jackets") -> dict:
    return {
        "url": url,
        "final_url": url,
        "title": "500 wholesale jackets",
        "query": "Deutschland Restposten Bekleidung Großhandel Lager",
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


def _build_result():
    module = _load_script()
    return module.build_checkpoint_result_from_exact_lots(
        [_strict_row()],
        market="DE",
        query_count=3,
        hit_count=15,
        verification={"exact_lot_candidate_count": 0},
        multihop={"exact_lot_candidate_count": 1, "gateway_page_count": 2},
    )


def test_strict_exact_lot_becomes_checkpoint_top5_but_not_financially_analyzed() -> None:
    result = _build_result()

    assert result["search_run_report"]["status"] == "SUCCESS"
    assert result["search_run_report"]["strict_exact_lot_count"] == 1
    assert result["search_run_report"]["top5_count"] == 1
    candidate = result["all_discovered_candidates"][0]
    assert candidate["opportunity_state"] == "CONFIRMED_SALE"
    assert candidate["listing_status"] == "ACTIVE"
    assert candidate["top5_eligible"] is True
    assert candidate["analysis_eligible"] is False
    assert candidate["verification"][0]["verified"] is True

    unified = build_unified_opportunity_report(
        result,
        market_code="DE",
        currency="EUR",
        domain="CLOTHING_INVENTORY",
    )
    assert unified["conversion_error_count"] == 0
    assert unified["record_count"] == 1
    record = unified["records"][0]
    assert record["workflow_status"] == "REQUIRES_VERIFICATION"
    assert record["evaluation_status"] == "REQUIRES_VERIFICATION"
    assert record["top5_eligible"] is True
    assert record["analysis_eligible"] is False
    assert record["source_provider"] == "EXA"


def test_search_report_emits_parseable_utc_discovered_at_for_source_continuity() -> None:
    report = _build_result()["search_run_report"]

    parsed = _time(report["discovered_at"])
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_exact_lot_rows_fail_closed_when_any_strict_evidence_is_missing() -> None:
    module = _load_script()
    row = _strict_row()
    row["evidence"]["quantity_evidence"] = False
    assert module._exact_lot_rows({"verified_pages": []}, {"exact_lots": [row]}) == []


def test_numeric_product_slug_gets_readable_fallback_title() -> None:
    module = _load_script()
    assert module._title_from_url("https://grossist.example/parti/2359") == "Clothing Exact-Lot 2359"


def test_exa_exact_lot_runner_covers_all_existing_six_markets() -> None:
    module = _load_script()
    assert tuple(module.MARKET_EXACT_LOT_QUERY_PACKS) == ("NO", "SE", "DE", "FR", "IT", "NL")
    assert set(module.MARKET_CURRENCIES) == {"NO", "SE", "DE", "FR", "IT", "NL"}
    for market in ("FR", "IT", "NL"):
        assert module.MARKET_EXACT_LOT_QUERY_PACKS[market] == (MARKET_EXACT_LOT_QUERIES[market],)
        assert len(module.MARKET_ZERO_YIELD_RECALL_QUERIES[market]) == 1
        fallback = module.MARKET_ZERO_YIELD_RECALL_QUERIES[market][0]
        assert _market_anchored(fallback, market)
        assert classify_project_domain(text=fallback) == CLOTHING_INVENTORY
        assert "site:" not in fallback.casefold()


def test_human_approved_de_challenge_uses_one_existing_primary_slot(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_script()
    searches: list[str] = []

    class FakeProvider:
        def __init__(self, _key: str):
            pass

        def search(self, query: str, *, count: int):
            searches.append(query)
            return []

    monkeypatch.setattr(module, "ExaSearchProvider", FakeProvider)
    monkeypatch.setattr(
        module,
        "verify_provider_unique_pages",
        lambda *_args, **_kwargs: {
            "verified_pages": [],
            "exact_lot_candidate_count": 0,
        },
    )
    monkeypatch.setattr(
        module,
        "resolve_exact_lot_multihop",
        lambda *_args, **_kwargs: {
            "exact_lots": [],
            "exact_lot_candidate_count": 0,
            "gateway_page_count": 0,
        },
    )
    memory = {
        "schema_version": "unified-memory-2.0",
        "status": "SUCCESS",
        "project_domain_gate_enforced": True,
        "query_memory": [],
    }

    result = module.run_market(
        market="DE",
        exa_api_key="test-key",
        output_dir=tmp_path,
        results_per_query=5,
        search_policy_memory=memory,
    )

    assert searches == [
        CHALLENGES["DE"]["challenger_query"],
        module.MARKET_EXACT_LOT_QUERY_PACKS["DE"][1],
    ]
    assert result["search_run_report"]["primary_query_count"] == 2
    challenge = result["search_run_report"]["search_policy_query_challenge"]
    assert challenge["status"] == "ACTIVE"
    assert challenge["request_slots_added"] == 0

    resolution = json.loads(
        (tmp_path / "exa-exact-lot-resolution.json").read_text(encoding="utf-8")
    )
    assert resolution["queries"][0]["query_stage"] == POLICY_CHALLENGE_STAGE
    assert resolution["queries"][0]["search_policy_challenge"]["request_slots_added"] == 0


def test_zero_yield_recall_runs_only_after_primary_strict_zero(monkeypatch, tmp_path: Path) -> None:
    module = _load_script()
    searches: list[str] = []
    verification_calls = 0

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
        nonlocal verification_calls
        verification_calls += 1
        return {"verified_pages": [], "exact_lot_candidate_count": 0}

    def fake_multihop(_verification, **_kwargs):
        if verification_calls == 1:
            return {
                "exact_lots": [],
                "exact_lot_candidate_count": 0,
                "gateway_page_count": 1,
            }
        row = _strict_row("https://example.test/product/55-pezzi-abbigliamento")
        row["query"] = module.MARKET_ZERO_YIELD_RECALL_QUERIES["IT"][0]
        return {
            "exact_lots": [row],
            "exact_lot_candidate_count": 1,
            "gateway_page_count": 1,
        }

    monkeypatch.setattr(module, "ExaSearchProvider", FakeProvider)
    monkeypatch.setattr(module, "verify_provider_unique_pages", fake_verify)
    monkeypatch.setattr(module, "resolve_exact_lot_multihop", fake_multihop)

    result = module.run_market(
        market="IT",
        exa_api_key="test-key",
        output_dir=tmp_path,
        results_per_query=5,
    )

    assert searches == [
        MARKET_EXACT_LOT_QUERIES["IT"],
        module.MARKET_ZERO_YIELD_RECALL_QUERIES["IT"][0],
    ]
    report = result["search_run_report"]
    assert report["strict_exact_lot_count"] == 1
    assert report["primary_strict_exact_lot_count"] == 0
    assert report["zero_yield_recall_triggered"] is True
    assert report["zero_yield_recall_query_count"] == 1
    assert report["zero_yield_recall_added_exact_lot_count"] == 1
    assert report["queries_submitted"] == 2

    resolution = json.loads((tmp_path / "exa-exact-lot-resolution.json").read_text())
    assert [row["query_stage"] for row in resolution["queries"]] == [
        "PRIMARY",
        "ZERO_YIELD_RECALL",
    ]
    assert resolution["adaptive_zero_yield_recall"]["triggered"] is True


def test_zero_yield_recall_is_not_spent_when_primary_already_has_exact_lot(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_script()
    searches: list[str] = []

    class FakeProvider:
        def __init__(self, _key: str):
            pass

        def search(self, query: str, *, count: int):
            searches.append(query)
            return [
                SearchHit(
                    title="Wholesale clothing stock",
                    url="https://example.test/root",
                    description="clothing stock wholesale",
                    provider="exa",
                )
            ][:count]

    def fake_verify(_benchmark, **_kwargs):
        return {"verified_pages": [], "exact_lot_candidate_count": 0}

    def fake_multihop(_verification, **_kwargs):
        row = _strict_row("https://example.test/product/2174-stuks-kleding")
        return {
            "exact_lots": [row],
            "exact_lot_candidate_count": 1,
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

    assert searches == [MARKET_EXACT_LOT_QUERIES["NL"]]
    report = result["search_run_report"]
    assert report["primary_strict_exact_lot_count"] == 1
    assert report["zero_yield_recall_triggered"] is False
    assert report["zero_yield_recall_query_count"] == 0
    assert report["queries_submitted"] == 1


def test_existing_core_exa_databases_remain_restorable_across_daily_checkpoints() -> None:
    assert "no-exa-exact-lot/opportunity_engine.db" in DATABASE_RELATIVE_PATHS
    assert "se-exa-exact-lot/opportunity_engine.db" in DATABASE_RELATIVE_PATHS
    assert "de-exa-exact-lot/opportunity_engine.db" in DATABASE_RELATIVE_PATHS
