from __future__ import annotations

import importlib.util
from pathlib import Path

from opportunity_engine.discovery.exa_exact_lot_shadow_hunt import MARKET_EXACT_LOT_QUERIES
from opportunity_engine.discovery.search_provider import SearchHit


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_exa_exact_lot_checkpoint.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_exa_exact_lot_checkpoint_fresh_recall", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _strict_row(url: str, *, provider: str = "exa") -> dict:
    return {
        "url": url,
        "final_url": url,
        "title": "500 wholesale clothing pieces",
        "query": MARKET_EXACT_LOT_QUERIES["FR"],
        "provider": provider,
        "retrieval_provenance": (
            "PROVEN_ROUTE_RECOVERY" if provider == "proven_route_recovery" else "DIRECT_SEARCH_RESULT"
        ),
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


def test_fresh_coverage_snapshot_separates_recovery_from_current_routes() -> None:
    module = _load_script()
    rows = [
        _strict_row("https://fresh.example/lot/1"),
        _strict_row("https://memory-a.example/lot/2", provider="proven_route_recovery"),
        _strict_row("https://memory-b.example/lot/3", provider="proven_route_recovery"),
    ]

    snapshot = module._fresh_coverage_snapshot(rows)

    assert snapshot["total_strict_exact_lot_count"] == 3
    assert snapshot["fresh_current_strict_exact_lot_count"] == 1
    assert snapshot["reverified_recovery_strict_exact_lot_count"] == 2
    assert snapshot["fresh_current_route_host_count"] == 1
    assert snapshot["fresh_current_route_hosts"] == ["fresh.example"]
    assert module._recovery_masks_fresh_coverage(snapshot) is True


def test_recovery_cannot_suppress_recall_when_fresh_search_is_thin(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_script()
    searches: list[str] = []
    evaluation_count = 0

    class FakeProvider:
        def __init__(self, _key: str):
            pass

        def search(self, query: str, *, count: int):
            searches.append(query)
            return [
                SearchHit(
                    title="Wholesale clothing stock",
                    url=f"https://search-result-{len(searches)}.example/root",
                    description="clothing stock wholesale",
                    provider="exa",
                )
            ][:count]

    def fake_verify(_benchmark, **_kwargs):
        return {"verified_pages": [], "exact_lot_candidate_count": 0}

    def fake_multihop(_verification, **_kwargs):
        nonlocal evaluation_count
        evaluation_count += 1
        rows = [
            _strict_row("https://fresh-one.example/lot/1"),
            _strict_row("https://memory-a.example/lot/2", provider="proven_route_recovery"),
            _strict_row("https://memory-b.example/lot/3", provider="proven_route_recovery"),
        ]
        if evaluation_count >= 2:
            recalled = _strict_row("https://fresh-two.example/lot/4")
            recalled["query"] = module.MARKET_ZERO_YIELD_RECALL_QUERIES["FR"][0]
            rows.append(recalled)
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
        results_per_query=1,
    )

    assert searches == [
        MARKET_EXACT_LOT_QUERIES["FR"],
        module.MARKET_ZERO_YIELD_RECALL_QUERIES["FR"][0],
    ]
    report = result["search_run_report"]
    assert report["primary_strict_exact_lot_count"] == 3
    assert report["primary_fresh_current_strict_exact_lot_count"] == 1
    assert report["primary_reverified_recovery_strict_exact_lot_count"] == 2
    assert report["zero_yield_recall_triggered"] is False
    assert report["fresh_recall_triggered"] is True
    assert report["fresh_recall_recovery_mask_triggered"] is True
    assert report["fresh_recall_query_count"] == 1
    assert report["fresh_recall_added_fresh_current_exact_lot_count"] == 1
    assert report["final_fresh_current_route_host_count"] == 2
    assert report["queries_submitted"] == 2
