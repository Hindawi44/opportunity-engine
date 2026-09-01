from __future__ import annotations

import importlib.util
from pathlib import Path

from opportunity_engine.discovery.search_provider import SearchHit


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_exa_exact_lot_checkpoint.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_exa_exact_lot_checkpoint_discovery_dedupe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cosmetic_discovery_urls_count_once_before_anchor_gate(monkeypatch, tmp_path: Path) -> None:
    module = _load_runner()
    base = "https://grossist.se/restpartier/1/20/parti/2359"

    class FakeProvider:
        def __init__(self, _key: str):
            pass

        def search(self, _query: str, *, count: int):
            return [
                SearchHit(
                    title="Kläder restparti 2359",
                    url=base,
                    description="kläder restparti säljes",
                    provider="exa",
                ),
                SearchHit(
                    title="Kläder restparti 2359",
                    url="https://www.grossist.se/restpartier/1/20/parti/2359/",
                    description="samma kommersiella sida",
                    provider="exa",
                ),
                SearchHit(
                    title="Kläder restparti 2359 variant",
                    url=f"{base}?variant=2",
                    description="distinkt query-identitet",
                    provider="exa",
                ),
            ][:count]

    def fake_verify(_benchmark, **_kwargs):
        return {"verified_pages": [], "exact_lot_candidate_count": 0}

    def fake_multihop(_verification, **_kwargs):
        return {"exact_lots": [], "exact_lot_candidate_count": 0, "gateway_page_count": 0}

    monkeypatch.setattr(module, "ExaSearchProvider", FakeProvider)
    monkeypatch.setattr(module, "verify_provider_unique_pages", fake_verify)
    monkeypatch.setattr(module, "resolve_exact_lot_multihop", fake_multihop)
    monkeypatch.setitem(module.MARKET_ZERO_YIELD_RECALL_QUERIES, "SE", ())
    monkeypatch.setattr(module, "COMMERCIAL_ANCHOR_MIN_UNIQUE_DISCOVERY_HITS", 3)
    monkeypatch.setattr(module, "COMMERCIAL_ANCHOR_MIN_UNIQUE_DISCOVERY_HITS_BY_MARKET", {})
    monkeypatch.setattr(
        module,
        "build_commercial_anchor_queries",
        lambda **_kwargs: [
            {
                "query": "Sverige kläder grossist lager parti",
                "anchor_type": "COMPANY",
                "anchor_value": "example",
                "anchor_origin": "test",
            }
        ],
    )

    result = module.run_market(
        market="SE",
        exa_api_key="test-key",
        output_dir=tmp_path,
        results_per_query=5,
    )

    report = result["search_run_report"]
    assert report["commercial_anchor_pre_unique_discovery_hit_count"] == 2
    assert report["commercial_anchor_min_unique_discovery_hits"] == 3
    assert report["commercial_anchor_expansion_triggered"] is False
    assert report["commercial_anchor_query_count"] == 0
