from __future__ import annotations

from opportunity_engine.discovery.exa_shadow_page_verification import (
    EXACT_LOT_CANDIDATE,
    _classify_page,
    _looks_item_specific_url,
)


def test_generic_german_shoes_products_category_is_not_item_specific() -> None:
    url = "https://salzmann-restwaren.de/products/schuhe/"
    assert _looks_item_specific_url(url) is False

    classification, evidence = _classify_page(
        title="Schuhe",
        text=(
            "Restposten Schuhe. Verfügbare Menge 120 Stk. Preis 4,99 EUR. "
            "In den Warenkorb."
        ),
        url=url,
    )

    assert classification != EXACT_LOT_CANDIDATE
    assert evidence["item_specific_url_evidence"] is False


def test_specific_german_shoes_restposten_product_remains_item_specific() -> None:
    url = "https://example.de/product/restposten-schuhe-120-paar/"
    assert _looks_item_specific_url(url) is True
