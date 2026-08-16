from __future__ import annotations

from opportunity_engine.discovery import market_comparables_target_hydration as hydration


def test_bauer_title_does_not_treat_half_pallet_descriptor_as_brand() -> None:
    brands = hydration._infer_brands("Halv pall med Bauer jakker")

    assert brands == ["Bauer"]


def test_real_brand_at_title_start_is_preserved() -> None:
    assert hydration._infer_brands("Nike jakker") == ["Nike"]


def test_descriptor_only_title_does_not_invent_a_brand() -> None:
    assert hydration._infer_brands("Halv pall med jakker") == []


def test_comparable_query_uses_bauer_without_half_pallet_noise() -> None:
    title = "Halv pall med Bauer jakker"
    query = hydration.quality_query_core(
        {
            "title": title,
            "brands": hydration._infer_brands(title),
            "source_url": "https://www.auksjonen.no/auksjon/example/123456",
        }
    )

    assert '"Bauer"' in query
    assert "halv" not in query.casefold().split()
    assert "pall" not in query.casefold().split()
