from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from opportunity_engine.discovery.commercial_anchor_query_expansion import (
    build_commercial_anchor_queries,
)
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_exa_exact_lot_checkpoint.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_exa_exact_lot_checkpoint_de_gate", SCRIPT)
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


def test_de_uses_narrow_lower_anchor_gate_while_other_markets_keep_default() -> None:
    module = _load_runner()
    assert module._commercial_anchor_min_unique_discovery_hits("DE") == 6
    for market in ("NO", "SE", "FR", "IT", "NL"):
        assert module._commercial_anchor_min_unique_discovery_hits(market) == 8


def test_de_anchor_runs_with_seven_unique_hits_and_zero_exact_lots(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_runner()
    searches: list[str] = []
    evaluations = 0

    class FakeProvider:
        def __init__(self, _key: str):
            pass

        def search(self, query: str, *, count: int):
            searches.append(query)
            batch_sizes = (3, 2, 2, 2, 2)
            batch = len(searches) - 1
            size = min(count, batch_sizes[batch])
            return [
                SearchHit(
                    title="Wholesale clothing stock",
                    url=f"https://example.test/de/{batch + 1}/{index}",
                    description="clothing stock wholesale",
                    provider="exa",
                )
                for index in range(1, size + 1)
            ]

    def fake_verify(_benchmark, **_kwargs):
        return {"verified_pages": [], "exact_lot_candidate_count": 0}

    def fake_multihop(_verification, **_kwargs):
        nonlocal evaluations
        evaluations += 1
        if evaluations == 1:
            rows = []
        else:
            anchor_query = build_commercial_anchor_queries(
                market="DE", project_domain=CLOTHING_INVENTORY
            )[0]["query"]
            rows = [
                _strict_row(
                    "https://example.test/product/900-bekleidung",
                    anchor_query,
                )
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
        market="DE",
        exa_api_key="test-key",
        output_dir=tmp_path,
        results_per_query=5,
    )

    anchor_rows = build_commercial_anchor_queries(
        market="DE", project_domain=CLOTHING_INVENTORY
    )
    assert searches == [
        *module.MARKET_EXACT_LOT_QUERY_PACKS["DE"],
        *(row["query"] for row in anchor_rows),
    ]
    report = result["search_run_report"]
    assert report["commercial_anchor_pre_unique_discovery_hit_count"] == 7
    assert report["commercial_anchor_min_unique_discovery_hits"] == 6
    assert report["commercial_anchor_expansion_triggered"] is True
    assert report["commercial_anchor_query_count"] == len(anchor_rows)
    assert report["commercial_anchor_added_exact_lot_count"] == 1
    assert report["strict_exact_lot_count"] == 1

    resolution = json.loads((tmp_path / "exa-exact-lot-resolution.json").read_text())
    anchor = resolution["controlled_commercial_anchor_expansion"]
    assert anchor["min_unique_discovery_hits"] == 6
    assert anchor["pre_anchor_unique_discovery_hit_count"] == 7
    assert anchor["triggered"] is True
    assert anchor["anchor_is_qualification_evidence"] is False
