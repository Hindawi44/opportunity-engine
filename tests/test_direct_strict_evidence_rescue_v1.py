from __future__ import annotations

import importlib.util
from pathlib import Path

from opportunity_engine.discovery.exa_shadow_page_verification import (
    ACTIVE_STOCK_SIGNAL,
    EXACT_LOT_CANDIDATE,
)
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_exa_exact_lot_checkpoint.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_exa_exact_lot_checkpoint_rescue", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _direct_row(*, classification: str = ACTIVE_STOCK_SIGNAL) -> dict:
    return {
        "classification": classification,
        "url": "https://example.test/product/partij-herenkleding-jack-jones-1050-stuks/",
        "final_url": "https://example.test/product/partij-herenkleding-jack-jones-1050-stuks/",
        "title": "Wholesale clothing lot Jack & Jones 1050 pieces",
        "query": "Nederland kleding clothing Jack & Jones restpartij groothandel voorraad te koop",
        "evidence": {
            "project_domain": CLOTHING_INVENTORY,
            "item_specific_url_evidence": True,
            "inventory_evidence": True,
            "direct_sale_evidence": True,
            "price_evidence": True,
            "quantity_evidence": True,
            "qualified_b2b_sale_evidence": True,
        },
    }


def test_qualified_b2b_active_page_with_complete_strict_proof_is_rescued() -> None:
    module = _load_runner()
    row = _direct_row()

    rows = module._exact_lot_rows({"verified_pages": [row]}, {"exact_lots": []})

    assert len(rows) == 1
    assert rows[0]["exact_lot_origin"] == "DIRECT_SEARCH_RESULT"
    assert rows[0]["direct_strict_evidence_rescue"] == module.DIRECT_STRICT_EVIDENCE_RESCUE


def test_active_page_without_qualified_b2b_sale_proof_is_not_rescued() -> None:
    module = _load_runner()
    row = _direct_row()
    row["evidence"]["qualified_b2b_sale_evidence"] = False

    assert module._exact_lot_rows({"verified_pages": [row]}, {"exact_lots": []}) == []


def test_active_page_missing_any_strict_exact_lot_evidence_is_not_rescued() -> None:
    module = _load_runner()
    row = _direct_row()
    row["evidence"]["price_evidence"] = False

    assert module._exact_lot_rows({"verified_pages": [row]}, {"exact_lots": []}) == []


def test_standard_exact_lot_candidate_remains_standard_not_rescue() -> None:
    module = _load_runner()
    row = _direct_row(classification=EXACT_LOT_CANDIDATE)
    row["evidence"]["qualified_b2b_sale_evidence"] = False

    rows = module._exact_lot_rows({"verified_pages": [row]}, {"exact_lots": []})

    assert len(rows) == 1
    assert rows[0]["exact_lot_origin"] == "DIRECT_SEARCH_RESULT"
    assert "direct_strict_evidence_rescue" not in rows[0]


def test_brand_name_never_replaces_strict_evidence() -> None:
    module = _load_runner()
    row = _direct_row()
    row["title"] = "Pronovias clothing wholesale page"
    row["evidence"]["quantity_evidence"] = False

    assert module._exact_lot_rows({"verified_pages": [row]}, {"exact_lots": []}) == []
