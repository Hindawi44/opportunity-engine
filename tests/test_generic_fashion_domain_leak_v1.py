from __future__ import annotations

from opportunity_engine.discovery import exa_shadow_page_verification as verification
from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    OUT_OF_DOMAIN,
    classify_project_domain,
)


def test_generic_fashion_watch_title_is_out_of_domain() -> None:
    text = (
        "Damen Armbanduhren Damenuhren versch Modelle Analoguhren Fashion Uhren. "
        "Restposten zu verkaufen. Preis 199 EUR. Menge 50 Stück."
    )

    assert classify_project_domain(text=text) == OUT_OF_DOMAIN


def test_explicit_garment_evidence_still_allows_fashion_text() -> None:
    text = (
        "Fashion Damenbekleidung Restposten: 50 Kleider und Jacken zu verkaufen. "
        "Preis 199 EUR."
    )

    assert classify_project_domain(text=text) == CLOTHING_INVENTORY


def test_watch_product_page_cannot_pass_strict_exact_lot_gate() -> None:
    classification, evidence = verification._classify_page(
        title="Damen Armbanduhren Damenuhren versch Modelle Analoguhren Fashion Uhren",
        text=(
            "Restposten aktuell zu verkaufen. Preis 199 EUR. Menge 50 Stück. "
            "Warenlager verfügbar."
        ),
        url=(
            "https://salzmann-restwaren.de/product/"
            "damen-armbanduhren-damenuhren-versch-modelle-analoguhren-fashion-uhren/"
        ),
    )

    assert evidence["domain_evidence"] is False
    assert classification != verification.EXACT_LOT_CANDIDATE
