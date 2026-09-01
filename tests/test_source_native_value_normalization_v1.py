from __future__ import annotations

from opportunity_engine.discovery.source_native_value_normalization import (
    normalize_source_native_values,
)


def test_grossist_single_pair_normalizes_without_financial_promotion() -> None:
    result = normalize_source_native_values(
        market="SE",
        url="https://www.grossist.se/restpartier/1/20/parti/2359",
        price_candidates=["14 000,00 kr"],
        quantity_candidates=["Kvantitet 140"],
    )

    assert result["status"] == "NORMALIZED"
    assert result["normalized_price"] == {
        "source_token": "14 000,00 kr",
        "amount": 14000.0,
        "amount_decimal": "14000.00",
        "currency": "SEK",
    }
    assert result["normalized_quantity"]["amount"] == 140
    assert result["normalized_quantity"]["unit"] == "COUNT"
    assert result["derived_unit_cost"]["amount_decimal"] == "100.00"
    assert result["derived_unit_cost"]["currency"] == "SEK"
    assert result["financial_analysis_ready"] is False
    assert result["normalization_is_qualification_evidence"] is False


def test_cdon_multi_value_page_fails_closed_as_ambiguous() -> None:
    result = normalize_source_native_values(
        market="SE",
        url="https://cdon.se/produkt/parti-grossist-restparti-123",
        price_candidates=["299 kr", "999 kr", "1 699 kr"],
        quantity_candidates=["18 st", "20 st", "22 st"],
    )

    assert result["status"] == "AMBIGUOUS"
    assert result["normalized_price"] is None
    assert result["normalized_quantity"] is None
    assert result["derived_unit_cost"] is None
    assert result["financial_analysis_ready"] is False


def test_ambiguous_kr_is_not_inferred_on_non_market_host() -> None:
    result = normalize_source_native_values(
        market="SE",
        url="https://example.com/product/wholesale-clothing-lot-42",
        price_candidates=["929 kr"],
        quantity_candidates=["19 st"],
    )

    assert result["status"] == "UNSUPPORTED_OR_AMBIGUOUS_FORMAT"
    assert result["normalized_price"] is None
    assert result["normalized_quantity"]["amount"] == 19
    assert result["derived_unit_cost"] is None


def test_explicit_eur_price_can_normalize_on_eu_market() -> None:
    result = normalize_source_native_values(
        market="DE",
        url="https://example.de/lot/123",
        price_candidates=["1.234,50 EUR"],
        quantity_candidates=["50 Stück"],
    )

    # Stück is intentionally not supported yet: fail closed rather than guess.
    assert result["status"] == "UNSUPPORTED_OR_AMBIGUOUS_FORMAT"
    assert result["normalized_price"]["amount_decimal"] == "1234.50"
    assert result["normalized_price"]["currency"] == "EUR"
    assert result["normalized_quantity"] is None
