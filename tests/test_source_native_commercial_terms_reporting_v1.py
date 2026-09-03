from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_exa_exact_lot_checkpoint.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_exa_exact_lot_checkpoint_commercial_terms_capture", RUNNER
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_candidate_propagates_raw_commercial_terms_without_claiming_readiness() -> None:
    runner = _load_runner()
    row = {
        "url": "https://example.se/restpartier/1/20/parti/2359",
        "final_url": "https://example.se/restpartier/1/20/parti/2359",
        "title": "Clothing Exact-Lot 2359",
        "query": "Sverige restparti kläder grossist lager",
        "exact_lot_origin": "MULTI_HOP",
        "evidence": {
            "project_domain": "CLOTHING_INVENTORY",
            "item_specific_url_evidence": True,
            "inventory_evidence": True,
            "direct_sale_evidence": True,
            "price_evidence": True,
            "quantity_evidence": True,
            "source_native_value_capture_version": "SOURCE_NATIVE_VALUE_CAPTURE_V1",
            "source_native_price_candidates": ["14 000,00 kr"],
            "source_native_price_basis_candidates": ["Totalpris"],
            "source_native_quantity_candidates": ["Kvantitet 140"],
            "source_native_commercial_terms_capture_version": "SOURCE_NATIVE_COMMERCIAL_TERMS_CAPTURE_V1",
            "source_native_condition_candidates": ["Skick: Nytt"],
            "source_native_seller_identity_candidates": ["Säljare: Example Wholesale AB"],
            "source_native_fulfilment_candidates": ["Frakt: Köparen betalar frakt"],
            "source_native_commercial_terms_capture_is_qualification_evidence": False,
        },
    }

    candidate = runner._candidate_from_exact_lot(row, market="SE")

    assert candidate["source_native_commercial_terms_capture_version"] == (
        "SOURCE_NATIVE_COMMERCIAL_TERMS_CAPTURE_V1"
    )
    assert candidate["source_native_condition_candidates"] == ["Skick: Nytt"]
    assert candidate["source_native_seller_identity_candidates"] == [
        "Säljare: Example Wholesale AB"
    ]
    assert candidate["source_native_fulfilment_candidates"] == [
        "Frakt: Köparen betalar frakt"
    ]
    assert candidate["source_native_commercial_terms_capture_is_qualification_evidence"] is False
    assert candidate["analysis_eligible"] is False
    assert "condition" in candidate["missing_information"]
    assert "seller or company identity" in candidate["missing_information"]
    assert "pickup or shipping terms" in candidate["missing_information"]
    verification = candidate["verification"][0]
    assert verification["source_native_condition_candidates"] == ["Skick: Nytt"]
    assert verification["source_native_seller_identity_candidates"] == [
        "Säljare: Example Wholesale AB"
    ]
    assert verification["source_native_fulfilment_candidates"] == [
        "Frakt: Köparen betalar frakt"
    ]
