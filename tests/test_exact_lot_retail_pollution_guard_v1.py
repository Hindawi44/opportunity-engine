from __future__ import annotations

from opportunity_engine.discovery.exa_shadow_page_verification import (
    EXACT_LOT_CANDIDATE,
    _classify_page,
    _looks_item_specific_url,
)


def test_kviberg_retail_product_does_not_gain_exact_lot_specificity_from_sitewide_surplus_text() -> None:
    url = "https://shop.kvibergs.se/produkt/barn-camo-t-shirt-gra/"

    classification, evidence = _classify_page(
        title="Barn Camo T-shirt Grå - Kvibergs Överskottslager",
        text=(
            "Kvibergs Överskottslager. T-shirt till salu. Pris 199 kr. "
            "Kvantitet 1 st. Kläder och mode."
        ),
        url=url,
    )

    assert _looks_item_specific_url(url) is False
    assert evidence["item_specific_url_evidence"] is False
    assert classification != EXACT_LOT_CANDIDATE


def test_salzmann_nested_categories_and_pagination_are_not_exact_lot_specific() -> None:
    assert (
        _looks_item_specific_url(
            "https://salzmann-restwaren.de/products/bekleidung/damenbekleidung/"
        )
        is False
    )
    assert (
        _looks_item_specific_url(
            "https://salzmann-restwaren.de/products/bekleidung/page/2/"
        )
        is False
    )


def test_existing_commercial_lot_product_routes_remain_specific() -> None:
    urls = (
        "https://friptadium.com/products/hauts-femme-au-kilo",
        "https://vinqa-grossiste.com/products/box-shorts-de-marque-x20",
        "https://cubecompany.nl/product/partij-dames-heren-en-kinderkleding-in-gold-we-trust-2-174-stuks/",
        "https://www.stockoutlet.it/stock/donna/calzature-donna/stock-sneakers-donna-shopart/",
        "https://www.grossist.se/restpartier/1/20/parti/2359",
    )

    for url in urls:
        assert _looks_item_specific_url(url) is True
