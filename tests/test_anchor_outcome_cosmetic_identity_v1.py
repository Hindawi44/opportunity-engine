from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_exa_exact_lot_checkpoint.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_exa_exact_lot_checkpoint_anchor_identity", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _anchor_query_row(query: str) -> dict:
    return {
        "query": query,
        "query_stage": "COMMERCIAL_ANCHOR",
        "commercial_anchor": {
            "type": "COMPANY",
            "value": "Grossist",
            "origin": "test",
        },
    }


def _lot(url: str, *, query: str) -> dict:
    return {
        "url": url,
        "final_url": url,
        "query": query,
    }


def test_cosmetic_url_variant_is_not_false_anchor_added_exact_lot() -> None:
    module = _load_runner()
    anchor_query = "Sverige kläder grossist lager parti"
    base = "https://grossist.se/restpartier/1/20/parti/2359"
    cosmetic = "https://www.grossist.se/restpartier/1/20/parti/2359/"

    evidence = module._commercial_anchor_outcome_evidence(
        market="SE",
        query_rows=[_anchor_query_row(anchor_query)],
        pre_anchor_exact_lots=[_lot(base, query="primary")],
        final_exact_lots=[_lot(cosmetic, query=anchor_query)],
    )

    assert evidence["pre_anchor_strict_exact_lot_count"] == 1
    assert evidence["post_anchor_strict_exact_lot_count"] == 1
    assert evidence["added_strict_exact_lot_count"] == 0
    assert evidence["attributed_added_strict_exact_lot_count"] == 0
    assert evidence["unattributed_added_strict_exact_lot_count"] == 0
    assert evidence["successful_outcome_count"] == 0
    assert evidence["attribution_complete"] is True
    assert evidence["outcomes"][0]["outcome"] == "NO_NEW_STRICT_EXACT_LOT"
    assert evidence["outcomes"][0]["strict_exact_lot_added_count"] == 0
    assert evidence["outcomes"][0]["strict_exact_lot_urls"] == []


def test_query_parameter_variant_remains_distinct_anchor_added_exact_lot() -> None:
    module = _load_runner()
    anchor_query = "Sverige kläder grossist lager parti"
    base = "https://grossist.se/restpartier/1/20/parti/2359"
    cosmetic = "https://www.grossist.se/restpartier/1/20/parti/2359/"
    variant = f"{base}?variant=2"

    evidence = module._commercial_anchor_outcome_evidence(
        market="SE",
        query_rows=[_anchor_query_row(anchor_query)],
        pre_anchor_exact_lots=[_lot(base, query="primary")],
        final_exact_lots=[
            _lot(cosmetic, query="primary"),
            _lot(variant, query=anchor_query),
        ],
    )

    assert evidence["pre_anchor_strict_exact_lot_count"] == 1
    assert evidence["post_anchor_strict_exact_lot_count"] == 2
    assert evidence["added_strict_exact_lot_count"] == 1
    assert evidence["attributed_added_strict_exact_lot_count"] == 1
    assert evidence["unattributed_added_strict_exact_lot_count"] == 0
    assert evidence["successful_outcome_count"] == 1
    assert evidence["attribution_complete"] is True
    assert evidence["outcomes"][0]["outcome"] == "STRICT_EXACT_LOT_SUCCESS"
    assert evidence["outcomes"][0]["strict_exact_lot_added_count"] == 1
    assert evidence["outcomes"][0]["strict_exact_lot_urls"] == [variant]
