from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.sweden_blinto import (
    _inventory_type,
    _quantity,
    _scenario_from_item_context,
    blinto_gate_decision,
)


def test_gate_rejects_clothing_printing_press_as_equipment() -> None:
    decision = blinto_gate_decision(
        SearchHit(
            title="Tryckpress - Thermal transfer press för kläder | Blinto auktioner",
            url="https://www.blinto.se/auction/Thermal-transfer-press-for-klader-153894-57776/",
            description="Tryckpress med tillbehör och 25 st transferark.",
            provider="Brave Search",
        )
    )

    assert decision.accepted is False
    assert decision.reason == "clothing-related equipment is not clothing inventory"


def test_blinto_lot_quality_recognizes_workwear_and_large_lot() -> None:
    text = "Parti arbetsbyxor från L.Brador och Blåkläder, 53 överdelar."

    assert _inventory_type(text) == "workwear_inventory"
    assert _scenario_from_item_context(text) == "LARGE_LOT_SALE"
    assert _quantity(text) == 53


def test_blinto_quantity_sums_explicit_multi_item_counts() -> None:
    text = "Skinnbyxor 3 par, regnoverall 3 st och skinnjackor 6 st."

    assert _quantity(text) == 12
