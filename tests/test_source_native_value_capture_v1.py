from __future__ import annotations

import importlib.util
from pathlib import Path

from opportunity_engine.discovery import exa_shadow_page_verification as verifier


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_exa_exact_lot_checkpoint.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_exa_exact_lot_checkpoint_value_capture", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_classification_captures_bounded_source_native_price_and_quantity_tokens() -> None:
    classification, evidence = verifier._classify_page(
        title="Parti grossist restparti blandade kläder",
        text=(
            "Till salu. Vald Bodyconklänningar Nude (19 st). "
            "Pris 929 kr. Alternativ 20 st. Pris 1 228 kr. "
            "Varulager för grossist."
        ),
        url="https://cdon.se/produkt/parti-grossist-restparti-blandade-klader-123456",
    )

    assert classification == verifier.EXACT_LOT_CANDIDATE
    assert evidence["price_evidence"] is True
    assert evidence["quantity_evidence"] is True
    assert evidence["source_native_value_capture_version"] == "SOURCE_NATIVE_VALUE_CAPTURE_V1"
    assert evidence["source_native_price_candidates"] == ["929 kr", "1 228 kr"]
    assert evidence["source_native_quantity_candidates"] == ["19 st", "20 st"]
    assert evidence["source_native_price_basis_candidates"] == []


def test_value_capture_is_bounded_and_deduplicated() -> None:
    text = " ".join(["100 kr 20 st"] * 20)
    _, evidence = verifier._classify_page(
        title="Parti kläder till salu",
        text=text,
        url="https://example.se/product/wholesale-clothing-lot-42",
    )

    assert evidence["source_native_price_candidates"] == ["100 kr"]
    assert evidence["source_native_quantity_candidates"] == ["20 st"]


def test_candidate_normalizes_single_unambiguous_pair_without_enabling_financial_analysis() -> None:
    runner = _load_runner()
    row = {
        "url": "https://example.se/product/wholesale-clothing-lot-42",
        "final_url": "https://example.se/product/wholesale-clothing-lot-42",
        "title": "Wholesale clothing lot",
        "query": "Sverige restparti kläder grossist lager",
        "exact_lot_origin": "DIRECT_SEARCH_RESULT",
        "evidence": {
            "project_domain": "CLOTHING_INVENTORY",
            "item_specific_url_evidence": True,
            "inventory_evidence": True,
            "direct_sale_evidence": True,
            "price_evidence": True,
            "quantity_evidence": True,
            "source_native_value_capture_version": "SOURCE_NATIVE_VALUE_CAPTURE_V1",
            "source_native_price_candidates": ["929 kr"],
            "source_native_price_basis_candidates": ["Pris for partiet"],
            "source_native_quantity_candidates": ["19 st"],
        },
    }

    candidate = runner._candidate_from_exact_lot(row, market="SE")

    assert candidate["source_native_value_capture_version"] == "SOURCE_NATIVE_VALUE_CAPTURE_V1"
    assert candidate["source_native_price_candidates"] == ["929 kr"]
    assert candidate["source_native_price_basis_candidates"] == ["Pris for partiet"]
    assert candidate["source_native_quantity_candidates"] == ["19 st"]
    assert candidate["source_value_normalization_required"] is False
    assert candidate["source_value_normalization"]["status"] == "NORMALIZED"
    assert candidate["source_value_normalization"]["normalized_price"]["amount"] == 929.0
    assert candidate["source_value_normalization"]["normalized_quantity"]["amount"] == 19
    assert candidate["source_value_normalization"]["derived_unit_cost"]["amount_decimal"] == "48.89"
    assert candidate["analysis_eligible"] is False


def test_classification_captures_explicit_per_item_price_basis() -> None:
    classification, evidence = verifier._classify_page(
        title="Lot de vêtements en vente",
        text="Stock de 750 pièces. Prix unitaire 3,50 EUR. Lot disponible.",
        url="https://example.fr/lot/vetements-750",
    )

    assert classification == verifier.EXACT_LOT_CANDIDATE
    assert evidence["source_native_price_basis_candidates"] == ["Prix unitaire"]
