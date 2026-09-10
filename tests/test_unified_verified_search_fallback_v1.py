from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from opportunity_engine.discovery import unified_search_runtime_cli_hook as search_runtime
from opportunity_engine.discovery.exa_shadow_page_verification import (
    EXACT_LOT_CANDIDATE,
    FETCH_FAILED,
)
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY, classify_project_domain
from opportunity_engine.production_search_outcome_bridge_v1 import _market_outcomes
from opportunity_engine.search_maturity_route_evidence_gate_v1 import (
    _clothing_provenance_assessment,
)
from opportunity_engine.search_experiment_execution_bridge_v1 import _market_anchored


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_exa_exact_lot_checkpoint.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("unified_verified_search_fallback", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _hit(url: str, *, provider: str) -> SearchHit:
    return SearchHit(
        title="500 wholesale clothing pieces",
        url=url,
        description="500 clothing pieces for sale, total price 1000",
        provider=provider,
    )


def _strict_page(url: str, *, provider: str, query: str) -> dict:
    return {
        "url": url,
        "final_url": url,
        "title": "500 wholesale clothing pieces",
        "query": query,
        "provider": provider,
        "classification": EXACT_LOT_CANDIDATE,
        "fetch_ok": True,
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


def _verification(*rows: dict) -> dict:
    return {
        "status": "SUCCESS",
        "verified_pages": list(rows),
        "exact_lot_candidate_count": len(rows),
        "page_fetches_attempted": len(rows),
        "page_fetches_succeeded": len(rows),
        "fetch_failed_count": 0,
        "unproven_page_count": 0,
    }


def _empty_multihop() -> dict:
    return {
        "status": "SUCCESS",
        "exact_lots": [],
        "exact_lot_candidate_count": 0,
        "gateway_page_count": 0,
        "navigation_page_fetches_attempted": 0,
        "navigation_page_fetches_succeeded": 0,
    }


def test_one_bounded_fallback_query_exists_for_every_market() -> None:
    module = _load_script()

    assert tuple(module.MARKET_BRAVE_FALLBACK_QUERIES) == (
        "NO",
        "SE",
        "DE",
        "FR",
        "IT",
        "NL",
    )
    assert module.BRAVE_FALLBACK_MAX_QUERIES_PER_MARKET == 1
    assert module._brave_fallback_reasons(
        {
            "fresh_current_strict_exact_lot_count": 3,
            "fresh_current_route_host_count": 2,
        },
        exa_search_error_count=1,
    ) == []
    for market, query in module.MARKET_BRAVE_FALLBACK_QUERIES.items():
        assert _market_anchored(query, market)
        assert classify_project_domain(text=query) == CLOTHING_INVENTORY
        assert "site:" not in query.casefold()


def test_strong_verified_exa_coverage_does_not_spend_brave(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_script()
    exa_hits = [
        _hit("https://one.example/lot/clothing-1", provider="Exa"),
        _hit("https://two.example/lot/clothing-2", provider="Exa"),
        _hit("https://two.example/lot/clothing-3", provider="Exa"),
    ]

    class FakeExa:
        def __init__(self, _key: str):
            pass

        def search(self, _query: str, *, count: int):
            return exa_hits[:count]

    class ForbiddenBrave:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("Brave must not be constructed for strong Exa coverage")

    def fake_verify(benchmark, *, provider: str, **_kwargs):
        assert provider == "exa"
        rows = []
        query = benchmark["market_results"][0]["query"]
        for raw in benchmark["market_results"][0]["exa"]["results"]:
            rows.append(_strict_page(raw["url"], provider="exa", query=query))
        return _verification(*rows)

    monkeypatch.setattr(module, "ExaSearchProvider", FakeExa)
    monkeypatch.setattr(module, "BraveSearchProvider", ForbiddenBrave)
    monkeypatch.setattr(module, "verify_provider_unique_pages", fake_verify)
    monkeypatch.setattr(module, "resolve_exact_lot_multihop", lambda *_a, **_k: _empty_multihop())

    result = module.run_market(
        market="NO",
        exa_api_key="exa-test",
        brave_api_key="brave-test",
        output_dir=tmp_path,
        results_per_query=5,
    )

    report = result["search_run_report"]
    assert report["strict_exact_lot_count"] == 3
    assert report["brave_fallback_required"] is False
    assert report["brave_fallback_triggered"] is False
    assert report["brave_fallback_query_count"] == 0
    assert report["brave_fallback_status"] == "NOT_REQUIRED"
    assert report["providers_used"] == ["EXA"]
    assert report["source_mode"] == module.EXA_SOURCE_MODE


def test_weak_exa_triggers_one_verified_brave_query_and_preserves_provider(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_script()
    brave_searches: list[tuple[str, int]] = []

    class FakeExa:
        def __init__(self, _key: str):
            pass

        def search(self, _query: str, *, count: int):
            return [_hit("https://exa.example/lot/clothing-1", provider="Exa")][:count]

    class FakeBrave:
        def __init__(self, _key: str, **kwargs):
            assert kwargs == {
                "country": "NO",
                "extra_snippets": True,
                "max_retries": 0,
            }

        def search(self, query: str, *, count: int):
            brave_searches.append((query, count))
            return [_hit("https://brave.example/lot/clothing-2", provider="Brave Search")]

    def fake_verify(benchmark, *, provider: str, **_kwargs):
        bucket = benchmark["market_results"][0][provider]
        query = benchmark["market_results"][0]["query"]
        rows = [
            _strict_page(raw["url"], provider=provider, query=query)
            for raw in bucket["results"]
        ]
        return _verification(*rows)

    monkeypatch.setattr(module, "ExaSearchProvider", FakeExa)
    monkeypatch.setattr(module, "BraveSearchProvider", FakeBrave)
    monkeypatch.setattr(module, "verify_provider_unique_pages", fake_verify)
    monkeypatch.setattr(module, "resolve_exact_lot_multihop", lambda *_a, **_k: _empty_multihop())

    result = module.run_market(
        market="NO",
        exa_api_key="exa-test",
        brave_api_key="brave-test",
        output_dir=tmp_path,
        results_per_query=5,
    )

    report = result["search_run_report"]
    assert brave_searches == [(module.MARKET_BRAVE_FALLBACK_QUERIES["NO"], 5)]
    assert report["brave_fallback_required"] is True
    assert report["brave_fallback_triggered"] is True
    assert report["brave_fallback_query_count"] == 1
    assert report["brave_fallback_status"] == "SUCCESS"
    assert report["brave_fallback_added_strict_exact_lot_count"] == 1
    assert report["strict_exact_lot_count"] == 2
    assert report["current_exa_discovery_strict_exact_lot_count"] == 1
    assert report["current_brave_fallback_strict_exact_lot_count"] == 1
    assert report["current_web_discovery_strict_exact_lot_count"] == 2
    assert report["providers_used"] == ["EXA", "BRAVE"]
    assert report["source_mode"] == module.HYBRID_SOURCE_MODE
    assert report["exact_lots_counted_only_after_live_page_verification"] is True
    brave_candidate = next(
        row for row in result["all_discovered_candidates"] if "brave.example" in row["source_urls"][0]
    )
    assert brave_candidate["source_providers"] == ["BRAVE"]
    assert brave_candidate["search_provider"] == "BRAVE"

    resolution = json.loads(
        (tmp_path / "exa-exact-lot-resolution.json").read_text(encoding="utf-8")
    )
    fallback = resolution["brave_verified_fallback"]
    assert fallback["query_count"] == 1
    assert fallback["verified_exact_lot_count"] == 1
    assert fallback["verification"]["page_fetches_succeeded"] == 1


def test_brave_fetch_failure_is_never_counted_as_an_exact_lot(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_script()

    class FakeExa:
        def __init__(self, _key: str):
            pass

        def search(self, _query: str, *, count: int):
            return []

    class FakeBrave:
        def __init__(self, _key: str, **_kwargs):
            pass

        def search(self, _query: str, *, count: int):
            return [_hit("https://dead.example/lot/clothing-9", provider="Brave Search")]

    def fake_verify(_benchmark, *, provider: str, **_kwargs):
        if provider == "exa":
            return _verification()
        failed = _strict_page(
            "https://dead.example/lot/clothing-9",
            provider="brave",
            query=module.MARKET_BRAVE_FALLBACK_QUERIES["NO"],
        )
        failed["classification"] = FETCH_FAILED
        failed["fetch_ok"] = False
        return {
            **_verification(),
            "verified_pages": [failed],
            "page_fetches_attempted": 1,
            "page_fetches_succeeded": 0,
            "fetch_failed_count": 1,
        }

    monkeypatch.setattr(module, "ExaSearchProvider", FakeExa)
    monkeypatch.setattr(module, "BraveSearchProvider", FakeBrave)
    monkeypatch.setattr(module, "verify_provider_unique_pages", fake_verify)
    monkeypatch.setattr(module, "resolve_exact_lot_multihop", lambda *_a, **_k: _empty_multihop())

    result = module.run_market(
        market="NO",
        exa_api_key="exa-test",
        brave_api_key="brave-test",
        output_dir=tmp_path,
        results_per_query=5,
    )

    report = result["search_run_report"]
    assert report["brave_fallback_status"] == "SUCCESS"
    assert report["brave_fallback_verified_exact_lot_count"] == 0
    assert report["strict_exact_lot_count"] == 0
    assert report["live_page_validation"]["fetch_failed_page_count"] == 1


def test_brave_cost_guard_failure_is_truthful_and_keeps_exa_result(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_script()

    class FakeExa:
        def __init__(self, _key: str):
            pass

        def search(self, _query: str, *, count: int):
            return [_hit("https://exa.example/lot/clothing-1", provider="Exa")][:count]

    class GuardedBrave:
        def __init__(self, _key: str, **_kwargs):
            pass

        def search(self, _query: str, *, count: int):
            raise RuntimeError("MANUAL_WORKFLOW_PAID_BRAVE_BLOCKED: zero-cost manual run")

    def fake_verify(benchmark, *, provider: str, **_kwargs):
        assert provider == "exa"
        query = benchmark["market_results"][0]["query"]
        return _verification(
            _strict_page(
                "https://exa.example/lot/clothing-1",
                provider="exa",
                query=query,
            )
        )

    monkeypatch.setattr(module, "ExaSearchProvider", FakeExa)
    monkeypatch.setattr(module, "BraveSearchProvider", GuardedBrave)
    monkeypatch.setattr(module, "verify_provider_unique_pages", fake_verify)
    monkeypatch.setattr(module, "resolve_exact_lot_multihop", lambda *_a, **_k: _empty_multihop())

    result = module.run_market(
        market="NO",
        exa_api_key="exa-test",
        brave_api_key="brave-test",
        output_dir=tmp_path,
        results_per_query=5,
    )

    report = result["search_run_report"]
    assert report["strict_exact_lot_count"] == 1
    assert report["brave_fallback_triggered"] is True
    assert report["brave_fallback_query_count"] == 1
    assert report["brave_fallback_status"] == "SKIPPED_COST_GUARD"
    assert report["providers_used"] == ["EXA"]
    assert report["source_mode"] == module.EXA_SOURCE_MODE


def test_weak_exa_without_brave_key_fails_closed_without_a_search_call(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_script()

    class FakeExa:
        def __init__(self, _key: str):
            pass

        def search(self, _query: str, *, count: int):
            return []

    class ForbiddenBrave:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("Brave must not run without a key")

    monkeypatch.setattr(module, "ExaSearchProvider", FakeExa)
    monkeypatch.setattr(module, "BraveSearchProvider", ForbiddenBrave)
    monkeypatch.setattr(module, "verify_provider_unique_pages", lambda *_a, **_k: _verification())
    monkeypatch.setattr(module, "resolve_exact_lot_multihop", lambda *_a, **_k: _empty_multihop())

    result = module.run_market(
        market="NO",
        exa_api_key="exa-test",
        output_dir=tmp_path,
        results_per_query=5,
    )

    report = result["search_run_report"]
    assert report["brave_fallback_required"] is True
    assert report["brave_fallback_triggered"] is False
    assert report["brave_fallback_query_count"] == 0
    assert report["brave_fallback_status"] == "SKIPPED_NO_API_KEY"


def test_total_provider_outage_is_reported_as_failure(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_script()

    class BrokenExa:
        def __init__(self, _key: str):
            pass

        def search(self, _query: str, *, count: int):
            raise RuntimeError("Exa Search request failed: unavailable")

    monkeypatch.setattr(module, "ExaSearchProvider", BrokenExa)
    monkeypatch.setattr(module, "verify_provider_unique_pages", lambda *_a, **_k: _verification())
    monkeypatch.setattr(module, "resolve_exact_lot_multihop", lambda *_a, **_k: _empty_multihop())

    result = module.run_market(
        market="NO",
        exa_api_key="exa-test",
        output_dir=tmp_path,
        results_per_query=5,
    )

    report = result["search_run_report"]
    assert report["status"] == "FAILURE"
    assert report["execution_status"] == "FAIL"
    assert report["retrieval_status"] == "FAILURE"
    assert report["successful_query_count"] == 0
    assert report["exa_search_error_count"] == 2
    assert report["brave_fallback_status"] == "SKIPPED_NO_API_KEY"


def test_hybrid_reporting_keeps_exa_and_brave_learning_provenance_separate() -> None:
    exa_query = "Norge klær vareparti pris antall stk"
    brave_query = "Norge klær restlager selges samlet pris stk"
    candidates = [
        {
            "canonical_urls": ["https://exa.example/lot/1"],
            "found_by_queries": [exa_query],
            "search_provider": "EXA",
            "retrieval_provenance": "DIRECT_SEARCH_RESULT",
        },
        {
            "canonical_urls": ["https://brave.example/lot/2"],
            "found_by_queries": [brave_query],
            "search_provider": "BRAVE",
            "retrieval_provenance": "DIRECT_SEARCH_RESULT",
        },
    ]
    report = {
        "market_code": "NO",
        "queries_submitted": 2,
        "strict_exact_lot_count": 2,
        "current_exa_discovery_strict_exact_lot_count": 1,
        "current_brave_fallback_strict_exact_lot_count": 1,
        "current_web_discovery_strict_exact_lot_count": 2,
        "freshly_reverified_recovery_exact_lot_count": 0,
    }
    resolution = {
        "schema_version": "exa-exact-lot-checkpoint-resolution-1.9",
        "generated_at": "2026-09-10T00:00:00+00:00",
        "market": "NO",
        "project_domain": CLOTHING_INVENTORY,
        "provider": "exa-primary-brave-fallback",
        "production_mutation": False,
        "queries": [
            {
                "query": exa_query,
                "query_stage": "PRIMARY",
                "provider": "exa",
                "status": "SUCCESS",
                "hits": [{"url": "https://exa.example/lot/1"}],
            },
            {
                "query": brave_query,
                "query_stage": "BRAVE_VERIFIED_FALLBACK",
                "provider": "brave",
                "status": "SUCCESS",
                "hits": [{"url": "https://brave.example/lot/2"}],
            },
        ],
    }

    records, summary = _market_outcomes(
        market="NO",
        resolution=resolution,
        candidates=candidates,
        report=report,
        source_path="no-exa-exact-lot/exa-exact-lot-resolution.json",
    )

    assert [row["provider"] for row in records] == ["exa", "brave"]
    assert [row["fresh_strict_exact_lot_count"] for row in records] == [1, 1]
    assert summary["fresh_strict_exact_lot_count"] == 2
    maturity = _clothing_provenance_assessment(report)
    assert maturity["provenance_counts_consistent"] is True
    assert maturity["current_exa_discovery_strict_exact_lot_count"] == 1
    assert maturity["current_web_discovery_strict_exact_lot_count"] == 2


def test_expansion_markets_receive_the_configured_brave_key(
    monkeypatch, tmp_path: Path
) -> None:
    calls: list[dict] = []
    input_root = tmp_path / "inputs"
    output_dir = tmp_path / "output"

    def run_market(**kwargs):
        calls.append(kwargs)
        return {
            "search_run_report": {
                "status": "SUCCESS",
                "strict_exact_lot_count": 0,
                "provider_strategy": "EXA_PRIMARY_BRAVE_VERIFIED_FALLBACK",
                "providers_used": ["EXA"],
                "brave_fallback_status": "NOT_REQUIRED",
            },
            "all_discovered_candidates": [],
        }

    fake_runner = SimpleNamespace(
        run_market=run_market,
        write_discovery_artifacts=lambda *_a, **_k: {},
        write_unified_opportunity_report=lambda *_a, **_k: tmp_path / "unified.json",
        MARKET_CURRENCIES={"FR": "EUR", "IT": "EUR", "NL": "EUR"},
    )
    monkeypatch.setenv("EXA_API_KEY", "exa-secret-present")
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "brave-secret-present")
    monkeypatch.setenv("INPUT_ROOT", str(input_root))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setattr(search_runtime, "_runner_module", lambda: fake_runner)

    search_runtime._run_expansion_clothing_exa()

    assert [call["market"] for call in calls] == ["FR", "IT", "NL"]
    assert all(call["exa_api_key"] == "exa-secret-present" for call in calls)
    assert all(call["brave_api_key"] == "brave-secret-present" for call in calls)
    status = json.loads(
        (output_dir / "unified-six-market-exa-runtime.json").read_text(
            encoding="utf-8"
        )
    )
    assert status["brave_fallback_available"] is True


def test_cycle_merge_does_not_mislabel_brave_only_yield_as_exa(
    tmp_path: Path,
) -> None:
    cycle_path = tmp_path / "cycle.json"
    cycle_path.write_text(
        json.dumps(
            {
                "status": "SUCCESS",
                "discovery_status": "VALID_ZERO",
                "exact_lot_verification": {},
            }
        ),
        encoding="utf-8",
    )

    search_runtime._merge_cycle_exact_truth(
        cycle_path,
        market="FR",
        report={
            "status": "SUCCESS",
            "strict_exact_lot_count": 1,
            "exa_strict_exact_lot_count": 0,
            "brave_fallback_verified_exact_lot_count": 1,
            "direct_exact_lot_count": 1,
            "multihop_exact_lot_count": 0,
            "source_mode": "EXA_PRIMARY_BRAVE_FALLBACK_MULTIHOP",
            "engine_version": "UNIFIED_EXA_PRIMARY_BRAVE_VERIFIED_FALLBACK_V1",
            "provider_strategy": "EXA_PRIMARY_BRAVE_VERIFIED_FALLBACK",
            "providers_used": ["EXA", "BRAVE"],
            "brave_fallback_status": "SUCCESS",
        },
        urls=["https://brave.example/lot/1"],
    )

    cycle = json.loads(cycle_path.read_text(encoding="utf-8"))
    exact = cycle["exact_lot_verification"]
    assert exact["exa_verified_active_exact_lot_count"] == 0
    assert exact["brave_fallback_verified_active_exact_lot_count"] == 1
    assert exact["unified_verified_active_exact_lot_count"] == 1
