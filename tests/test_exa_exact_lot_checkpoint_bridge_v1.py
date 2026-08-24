from __future__ import annotations

import importlib.util
from pathlib import Path

from opportunity_engine.discovery.unified_opportunity_report import build_unified_opportunity_report


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


def test_strict_exact_lot_becomes_checkpoint_top5_but_not_financially_analyzed() -> None:
    module = _load_script()
    result = module.build_checkpoint_result_from_exact_lots(
        [_strict_row()],
        market="DE",
        query_count=3,
        hit_count=15,
        verification={"exact_lot_candidate_count": 0},
        multihop={"exact_lot_candidate_count": 1, "gateway_page_count": 2},
    )

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


def test_exact_lot_rows_fail_closed_when_any_strict_evidence_is_missing() -> None:
    module = _load_script()
    row = _strict_row()
    row["evidence"]["quantity_evidence"] = False
    assert module._exact_lot_rows({"verified_pages": []}, {"exact_lots": [row]}) == []


def test_numeric_product_slug_gets_readable_fallback_title() -> None:
    module = _load_script()
    assert module._title_from_url("https://grossist.example/parti/2359") == "Clothing Exact-Lot 2359"
