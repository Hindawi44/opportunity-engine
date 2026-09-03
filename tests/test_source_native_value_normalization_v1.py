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
        price_basis_candidates=["Totalpris"],
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
    assert result["price_basis"] == "TOTAL"
    assert result["price_basis_evidence"] == ["captured_context:Totalpris"]
    assert result["derived_unit_cost"]["derivation"] == (
        "EXPLICIT_TOTAL_PRICE_DIVIDED_BY_NORMALIZED_COUNT"
    )
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


def test_bare_price_and_quantity_fail_closed_when_price_basis_is_unknown() -> None:
    result = normalize_source_native_values(
        market="FR",
        url="https://example.fr/lot/vestes",
        price_candidates=["3,50 EUR"],
        quantity_candidates=["750 pièces"],
    )

    assert result["status"] == "AMBIGUOUS_PRICE_BASIS"
    assert result["price_basis"] == "UNKNOWN"
    assert result["normalized_price"]["amount_decimal"] == "3.50"
    assert result["normalized_quantity"]["amount"] == 750
    assert result["derived_unit_cost"] is None


def test_explicit_french_per_item_price_is_not_divided_by_quantity() -> None:
    result = normalize_source_native_values(
        market="FR",
        url="https://example.fr/lot/vestes",
        price_candidates=["3,50 EUR"],
        quantity_candidates=["750 pièces"],
        price_basis_candidates=["Prix unitaire"],
    )

    assert result["status"] == "NORMALIZED"
    assert result["price_basis"] == "PER_ITEM"
    assert result["price_basis_evidence"] == [
        "captured_context:Prix unitaire"
    ]
    assert result["derived_unit_cost"]["amount_decimal"] == "3.50"
    assert result["derived_unit_cost"]["derivation"] == "SOURCE_PRICE_EXPLICITLY_PER_ITEM"


def test_italian_per_item_url_is_not_divided_by_quantity() -> None:
    result = normalize_source_native_values(
        market="IT",
        url=(
            "https://stockitaly24.com/products/17-00-al-pezzo-stock-abbigliamento-"
            "100-pezzi"
        ),
        price_candidates=["17,00 EUR"],
        quantity_candidates=["100 pezzi"],
    )

    assert result["status"] == "NORMALIZED"
    assert result["price_basis"] == "PER_ITEM"
    assert result["price_basis_evidence"] == ["source_url:al pezzo"]
    assert result["derived_unit_cost"]["amount_decimal"] == "17.00"
    assert result["derived_unit_cost"]["derivation"] == "SOURCE_PRICE_EXPLICITLY_PER_ITEM"
