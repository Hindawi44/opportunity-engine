from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery import unified_search_runtime_cli_hook as runtime
from opportunity_engine.discovery import six_market_fabric_coverage_rotation_v1 as coverage
from opportunity_engine.project_domain_boundary import FABRIC_PROCUREMENT, classify_project_domain


def test_fabric_exa_queries_cover_all_six_while_runtime_budget_stays_three() -> None:
    assert tuple(runtime.FABRIC_EXA_QUERIES) == runtime.SIX_MARKETS
    assert len(runtime.FABRIC_MARKETS) == coverage.FIXED_QUERY_BUDGET_PER_RUN == 3
    assert set(runtime.FABRIC_MARKETS).issubset(set(runtime.SIX_MARKETS))
    for market, query in runtime.FABRIC_EXA_QUERIES.items():
        assert market in runtime.SIX_MARKETS
        assert classify_project_domain(text=query) == FABRIC_PROCUREMENT
        assert "site:" not in query.casefold()


def test_fabric_rotation_covers_all_six_in_two_consecutive_seeds_without_budget_growth() -> None:
    first = coverage.select_fabric_market_cohort(seed=0)
    second = coverage.select_fabric_market_cohort(seed=1)

    assert len(first) == len(second) == 3
    assert set(first).isdisjoint(set(second))
    assert set(first) | set(second) == set(runtime.SIX_MARKETS)
    assert coverage.SEARCH_REQUESTS_ADDED_PER_RUN == 0
    assert coverage.PAGE_RESULT_BUDGET_ADDED_PER_RUN == 0
    assert coverage.FIXED_RESULTS_PER_QUERY == runtime.FABRIC_RESULTS_PER_MARKET == 5


def test_france_and_netherlands_not_implemented_truth_is_replaced_by_exa_exact_lot(tmp_path: Path) -> None:
    for market, filename in (("FR", "france.json"), ("NL", "netherlands.json")):
        path = tmp_path / filename
        path.write_text(
            json.dumps(
                {
                    "status": "SUCCESS",
                    "source_country": market,
                    "discovery_status": "BLOCKED_RETRIEVAL",
                    "discovery_accepted_signal_count": 0,
                    "exact_lot_verification_status": "NOT_BUILT_YET_REQUIRES_SOURCE_SPECIFIC_VALIDATION",
                    "automatic_purchase": False,
                }
            ),
            encoding="utf-8",
        )
        runtime._merge_cycle_exact_truth(
            path,
            market=market,
            report={
                "status": "SUCCESS",
                "strict_exact_lot_count": 2,
                "direct_exact_lot_count": 0,
                "multihop_exact_lot_count": 2,
                "source_mode": "EXA_EXACT_LOT_MULTIHOP",
                "query_pack": "SIX_MARKET_EXACT_LOT_PROVEN_V1",
            },
            urls=[f"https://example.test/{market.casefold()}/lot-1", f"https://example.test/{market.casefold()}/lot-2"],
        )
        cycle = json.loads(path.read_text(encoding="utf-8"))
        assert cycle["discovery_status"] == "SUCCESS"
        assert cycle["exact_lot_verification_status"] == "SUCCESS"
        assert cycle["exact_lot_verification"]["verified_active_exact_lot_lead_count"] == 2
        assert len(cycle["exact_lot_verification"]["verified_exact_lot_urls"]) == 2
        assert cycle["primary_search_provider"] == "exa"
        assert cycle["unified_market_coverage"] == ["NO", "SE", "DE", "FR", "IT", "NL"]
        assert cycle["country_specific_exact_lot_bypass"] is False


def test_italy_existing_positive_exact_lot_is_not_downgraded_by_exa_zero(tmp_path: Path) -> None:
    path = tmp_path / "italy.json"
    path.write_text(
        json.dumps(
            {
                "status": "SUCCESS",
                "source_country": "IT",
                "discovery_status": "SUCCESS",
                "exact_lot_verification": {
                    "status": "SUCCESS",
                    "candidate_lead_count": 3,
                    "source_page_verified_count": 3,
                    "verified_active_exact_lot_lead_count": 3,
                },
                "commercial_qualification": {"status": "SUCCESS", "qualification_count": 1},
            }
        ),
        encoding="utf-8",
    )
    runtime._merge_cycle_exact_truth(
        path,
        market="IT",
        report={
            "status": "SUCCESS",
            "strict_exact_lot_count": 0,
            "direct_exact_lot_count": 0,
            "multihop_exact_lot_count": 0,
            "source_mode": "EXA_EXACT_LOT_MULTIHOP",
            "query_pack": "SIX_MARKET_EXACT_LOT_PROVEN_V1",
        },
        urls=[],
    )
    cycle = json.loads(path.read_text(encoding="utf-8"))
    assert cycle["exact_lot_verification"]["verified_active_exact_lot_lead_count"] == 3
    assert cycle["exact_lot_verification_status"] == "SUCCESS"
    assert cycle["commercial_qualification"]["qualification_count"] == 1


def test_generic_exa_fabric_search_uses_rotated_three_market_budget_and_verified_page_gate(monkeypatch) -> None:
    class FakeProvider:
        def __init__(self, _key: str):
            pass

        def search(self, query: str, *, count: int):
            market = next(
                code for code, configured_query in runtime.FABRIC_EXA_QUERIES.items()
                if configured_query == query
            )
            return [
                SearchHit(
                    title=f"{market} fabric stock",
                    url=f"https://{market.casefold()}.example.test/fabric-lot",
                    description="wholesale stock price per meter",
                    provider="exa",
                )
            ][:count]

    def fake_page_candidate(hit: SearchHit, *, page_fetcher):
        return {
            "url": hit.url,
            "final_url": hit.url,
            "title": hit.title,
            "fetch_ok": True,
            "project_domain": "FABRIC_PROCUREMENT",
            "inventory_signal": True,
            "trade_or_price_signal": True,
            "commercial_fabric_page": True,
            "verification_decision": "ACCEPT",
            "rejection_reason": None,
        }

    monkeypatch.setattr(runtime, "ExaSearchProvider", FakeProvider)
    monkeypatch.setattr(runtime, "_fabric_page_candidate", fake_page_candidate)
    monkeypatch.setenv("EXA_API_KEY", "test-key")

    report = runtime._run_fabric_exa_search()

    assert report["status"] == "SUCCESS"
    assert report["market_coverage"] == list(runtime.FABRIC_MARKETS)
    assert report["scheduled_market_coverage"] == list(runtime.FABRIC_MARKETS)
    assert report["all_market_coverage"] == list(runtime.SIX_MARKETS)
    assert report["query_budget_total"] == 3
    assert report["query_budget_unchanged"] is True
    assert report["search_requests_added_by_coverage_rotation"] == 0
    assert report["requests_made"] == 3
    assert report["candidate_count"] == 3
    assert {row["source_country"] for row in report["candidates"]} == set(runtime.FABRIC_MARKETS)
    assert all(row["project_domain"] == "FABRIC_PROCUREMENT" for row in report["candidates"])
    assert all(row["top5_eligible"] is False for row in report["candidates"])
    assert all(row["automatic_purchase"] is False for row in report["candidates"])


def test_reconciliation_summary_exposes_all_six_fabric_markets_and_schedule_state() -> None:
    scheduled = tuple(runtime.FABRIC_MARKETS)
    ledger = {
        "search_runtime": {
            "CLOTHING_INVENTORY": {
                "markets": {
                    code: {"status": "SUCCESS", "hits_received": 1, "strict_exact_lot_count": 1}
                    for code in runtime.SIX_MARKETS
                }
            },
            "FABRIC_PROCUREMENT": {
                "market_coverage": list(scheduled),
                "scheduled_market_coverage": list(scheduled),
                "markets": {
                    code: {"status": "SUCCESS", "hits_received": 1, "candidate_count": 1}
                    for code in scheduled
                },
            },
        }
    }

    text = coverage._render_search_runtime_section_all_six(ledger)

    for code in runtime.SIX_MARKETS:
        assert f"{code} ملابس:" in text
        assert f"{code} أقمشة:" in text
    assert "3/6 أسواق في كل تشغيل" in text


def test_unified_operator_artifact_contains_both_domains_without_mixing_top5(tmp_path: Path) -> None:
    pipeline = tmp_path / runtime.UNIFIED_PIPELINE_FILENAME
    summary = tmp_path / runtime.UNIFIED_PHONE_SUMMARY_FILENAME
    pipeline.write_text(
        json.dumps(
            {
                "schema_version": "unified-six-market-pipeline-1.0",
                "market_coverage": ["NO", "SE", "DE", "FR", "IT", "NL"],
                "markets": [],
                "automatic_purchase": False,
            }
        ),
        encoding="utf-8",
    )
    summary.write_text("ملخص المسار الموحد — 6 أسواق\n", encoding="utf-8")
    clothing = {
        "markets": {
            code: {"status": "SUCCESS", "hits_received": 5, "strict_exact_lot_count": 1}
            for code in runtime.SIX_MARKETS
        }
    }
    fabric = {
        "markets": {
            code: {"status": "SUCCESS", "hits_received": 5, "verified_page_count": 3, "candidate_count": 1}
            for code in runtime.FABRIC_MARKETS
        }
    }

    runtime._append_unified_runtime(tmp_path, clothing=clothing, fabric=fabric)

    ledger = json.loads(pipeline.read_text(encoding="utf-8"))
    assert ledger["project_domains"] == ["CLOTHING_INVENTORY", "FABRIC_PROCUREMENT"]
    assert ledger["separated_country_search_paths"] is False
    assert ledger["fabric_is_first_class_project_domain"] is True
    assert ledger["fabric_mixed_into_clothing_top5"] is False
    text = summary.read_text(encoding="utf-8")
    assert "CLOTHING_INVENTORY" in text
    assert "FABRIC_PROCUREMENT" in text
    for code in runtime.SIX_MARKETS:
        assert f"{code}:" in text
