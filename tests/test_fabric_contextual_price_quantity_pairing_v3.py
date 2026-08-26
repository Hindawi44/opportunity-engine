from __future__ import annotations

from opportunity_engine.discovery.fabric_route_commercial_evidence_normalization_v1 import (
    normalize_fabric_commercial_evidence,
)


def test_rijs_italy_minimum_order_total_does_not_replace_local_tier_price() -> None:
    evidence = normalize_fabric_commercial_evidence(
        "Ordine minimo di 6 metri. Totale ordine minimo € 200. "
        "Prezzi: ≥ 6 Metri € 6,50 ≥ 12 Metri € 6,00 ≥ 50 Metri € 5,50",
        market="IT",
    )

    assert evidence["price"] == 6.5
    assert evidence["price_text"] == "€ 6,50"
    assert evidence["currency"] == "EUR"
    assert evidence["quantity"] == 6.0
    assert evidence["quantity_unit"] == "metri"
    assert evidence["commercial_evidence_complete"] is True
    assert evidence["commercial_evidence_pairing_mode"] == "CONTEXTUAL_PRICE_QUANTITY_PAIR"


def test_dutch_shipping_and_sample_prices_do_not_beat_outlet_quantity_tier() -> None:
    evidence = normalize_fabric_commercial_evidence(
        "Gratis verzending vanaf € 100. Staal € 0,50. "
        "Outlet: ≥ 6 Meter € 8,50 ≥ 12 Meter € 7,50",
        market="NL",
    )

    assert evidence["price"] == 8.5
    assert evidence["price_text"] == "€ 8,50"
    assert evidence["currency"] == "EUR"
    assert evidence["quantity"] == 6.0
    assert evidence["quantity_unit"] == "meter"
    assert evidence["commercial_evidence_complete"] is True


def test_area_rate_does_not_replace_roll_total_when_pairing_with_linear_quantity() -> None:
    evidence = normalize_fabric_commercial_evidence(
        "0,00 € cart. Dekomolton Stoffballen auf Lager. "
        "319,00 € brutto, 3,54 € pro m². Länge am Stück: 30 lfm, "
        "entspricht 90m² pro Ballen.",
        market="DE",
    )

    assert evidence["price"] == 319.0
    assert evidence["price_text"] == "319,00 €"
    assert evidence["quantity"] == 30.0
    assert evidence["quantity_unit"] == "lfm"
    assert evidence["commercial_evidence_complete"] is True


def test_prefix_price_without_local_quantity_pair_is_not_promoted_as_purchase_price() -> None:
    evidence = normalize_fabric_commercial_evidence(
        "Gratis verzending vanaf € 100. Fabric wholesale stock available.",
        market="NL",
    )

    assert evidence["price"] is None
    assert evidence["quantity"] is None
    assert evidence["commercial_evidence_complete"] is False
