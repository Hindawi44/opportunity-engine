from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_exa_exact_lot_checkpoint.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_exa_exact_lot_checkpoint_value_evidence", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _strict_row() -> dict:
    return {
        "url": "https://example.test/product/640-jackets",
        "final_url": "https://example.test/product/640-jackets",
        "title": "640 wholesale jackets",
        "query": "Sverige restparti kläder grossist lager",
        "exact_lot_origin": "DIRECT_SEARCH_RESULT",
        "evidence": {
            "project_domain": "CLOTHING_INVENTORY",
            "item_specific_url_evidence": True,
            "inventory_evidence": True,
            "direct_sale_evidence": True,
            "price_evidence": True,
            "quantity_evidence": True,
        },
    }


def test_exact_lot_does_not_claim_numeric_price_or_quantity_are_missing_after_regex_proof() -> None:
    module = _load_script()

    candidate = module._candidate_from_exact_lot(_strict_row(), market="SE")

    assert candidate["source_native_price_evidence_detected"] is True
    assert candidate["source_native_quantity_evidence_detected"] is True
    assert candidate["source_value_normalization_required"] is True
    assert candidate["analysis_eligible"] is False
    assert "exact numeric price value" not in candidate["missing_information"]
    assert "exact numeric quantity value" not in candidate["missing_information"]
    assert "normalized source-native price value for financial analysis" in candidate[
        "missing_information"
    ]
    assert "normalized source-native quantity value for financial analysis" in candidate[
        "missing_information"
    ]
    assert "source-native numeric price and quantity patterns were verified" in candidate[
        "verification"
    ][0]["bounded_context"]


def test_search_report_counts_value_evidence_without_changing_exact_lot_gate() -> None:
    module = _load_script()
    row = _strict_row()

    result = module.build_checkpoint_result_from_exact_lots(
        [row],
        market="SE",
        query_count=3,
        hit_count=15,
        verification={"exact_lot_candidate_count": 1},
        multihop={"exact_lot_candidate_count": 0, "gateway_page_count": 0},
    )

    report = result["search_run_report"]
    assert report["strict_exact_lot_count"] == 1
    assert report["source_native_value_evidence_count"] == 1
    assert report["source_value_normalization_required_count"] == 1
    assert result["all_discovered_candidates"][0]["top5_eligible"] is True
    assert result["all_discovered_candidates"][0]["analysis_eligible"] is False


def test_existing_strict_gate_still_fails_closed_when_quantity_evidence_is_absent() -> None:
    module = _load_script()
    row = _strict_row()
    row["evidence"]["quantity_evidence"] = False

    assert module._strict_exact_evidence(row=row, require_subject_evidence=False) is False
