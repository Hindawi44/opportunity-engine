from __future__ import annotations

from opportunity_engine.discovery.exact_lot_child_link_resolution import _classify_child_page
from opportunity_engine.discovery.exa_shadow_page_verification import (
    EXACT_LOT_CANDIDATE,
    _classify_page,
    _looks_item_specific_url,
)
from opportunity_engine.project_domain_boundary import OUT_OF_DOMAIN


def test_aggregate_lot_index_is_not_item_specific() -> None:
    assert _looks_item_specific_url("https://www.sdpie.com/lots-en-vente/") is False
    assert _looks_item_specific_url("https://example.com/lots/") is False
    assert _looks_item_specific_url("https://example.com/products/") is False
    assert _looks_item_specific_url("https://example.com/collections/femme-basic") is False
    assert _looks_item_specific_url("https://example.com/products/search") is False


def test_nested_single_lot_detail_remains_item_specific() -> None:
    assert (
        _looks_item_specific_url(
            "https://www.sdpie.com/lots-en-vente/lot-de-vestes-et-costumes/"
        )
        is True
    )


def test_plural_products_container_with_specific_slug_is_item_specific() -> None:
    assert (
        _looks_item_specific_url(
            "https://friptadium.com/products/hauts-femme-au-kilo"
        )
        is True
    )


def test_numeric_html_wholesale_product_detail_is_item_specific() -> None:
    url = (
        "https://bijuymoda.com/en/wholesale-mens-clothing/"
        "3347-wholesale-jack-jones-men-s-clothing-lot.html"
    )
    assert _looks_item_specific_url(url) is True
    assert (
        _looks_item_specific_url(
            "https://example.com/catalog/wholesale-mens-clothing/"
            "3347-wholesale-jack-jones-men-s-clothing-lot.html"
        )
        is False
    )


def test_numeric_html_wholesale_clothing_lot_can_be_exact_lot() -> None:
    classification, evidence = _classify_page(
        title="Wholesale Jack & Jones Men's Clothing Lot",
        text=(
            "Stock of men's clothing available for sale. Quantity: 120 pcs. "
            "Wholesale price 6 EUR per piece. Jack & Jones jackets and shirts."
        ),
        url=(
            "https://bijuymoda.com/en/wholesale-mens-clothing/"
            "3347-wholesale-jack-jones-men-s-clothing-lot.html"
        ),
    )

    assert classification == EXACT_LOT_CANDIDATE
    assert evidence["item_specific_url_evidence"] is True
    assert evidence["domain_evidence"] is True
    assert evidence["inventory_evidence"] is True
    assert evidence["direct_sale_evidence"] is True
    assert evidence["price_evidence"] is True
    assert evidence["quantity_evidence"] is True


def test_child_clothing_lot_accepts_number_then_euro_symbol_price() -> None:
    classification, evidence = _classify_child_page(
        title="Lot de vestes et pantalons costumes",
        text=(
            "Lots en vente. Stock de vêtements professionnels issu de fins de séries. "
            "Quantités : environ 250 pièces. Prix déstockage : 4 € HT/pc. "
            "Prix du lot 1000 € HT."
        ),
        url="https://www.sdpie.com/lots-en-vente/lot-de-vestes-et-costumes/",
    )

    assert classification == EXACT_LOT_CANDIDATE
    assert evidence["price_evidence"] is True
    assert evidence["quantity_evidence"] is True
    assert evidence["item_specific_url_evidence"] is True
    assert evidence["page_subject_domain"] == "CLOTHING_INVENTORY"
    assert evidence["project_domain"] == "CLOTHING_INVENTORY"


def test_canonical_clothing_product_can_prove_direct_sale_from_purchase_control() -> None:
    classification, evidence = _classify_child_page(
        title="Hauts femme au kilo à revendre",
        text=(
            "Stock de vêtements Grade A. Choisissez votre format. 3 kg 24,99 €. "
            "Environ 12 à 18 pièces. Ajouter au panier. Paiement sécurisé."
        ),
        url="https://friptadium.com/products/hauts-femme-au-kilo",
    )

    assert classification == EXACT_LOT_CANDIDATE
    assert evidence["canonical_product_detail_url_evidence"] is True
    assert evidence["explicit_purchase_evidence"] is True
    assert evidence["direct_sale_evidence"] is True
    assert evidence["price_evidence"] is True
    assert evidence["quantity_evidence"] is True
    assert evidence["page_subject_domain"] == "CLOTHING_INVENTORY"


def test_sitewide_cart_controls_do_not_turn_a_hub_page_into_exact_lot() -> None:
    classification, evidence = _classify_child_page(
        title="Lot de vêtements pour revendeur : guide et formats",
        text=(
            "Stock de vêtements pour revendeurs. Guide complet. Lots en vente. "
            "Formats 3 kg et 10 kg, prix de 24,99 € à 179,99 €. "
            "Article ajouté au panier. Procéder au paiement."
        ),
        url="https://friptadium.com/pages/lot-de-vetements-revendeur",
    )

    assert classification != EXACT_LOT_CANDIDATE
    assert evidence["canonical_product_detail_url_evidence"] is False
    assert evidence["explicit_purchase_evidence"] is False


def test_child_non_clothing_subject_is_not_polluted_by_navigation_text() -> None:
    classification, evidence = _classify_child_page(
        title="Lot de peinture blanche",
        text=(
            "Lots en vente. Stock de peinture blanche. Quantité : 10 palettes. "
            "Prix déstockage : 5000 €. Navigation: Chaussure Textile Linge de Maison; "
            "Lot de vêtements friperie; vêtements professionnels."
        ),
        url="https://www.sdpie.com/lots-en-vente/lot-de-peinture/",
    )

    assert classification == OUT_OF_DOMAIN
    assert evidence["item_specific_url_evidence"] is True
    assert evidence["page_subject_domain"] == OUT_OF_DOMAIN
    assert evidence["project_domain"] == OUT_OF_DOMAIN
    assert evidence["domain_evidence"] is False


def test_non_clothing_canonical_product_stays_out_of_domain_even_with_cart() -> None:
    classification, evidence = _classify_child_page(
        title="Peinture blanche professionnelle",
        text=(
            "Stock peinture. 3 kg 24,99 €. Environ 12 pièces. Ajouter au panier. "
            "Navigation vêtements mode textile."
        ),
        url="https://example.com/products/peinture-blanche",
    )

    assert classification == OUT_OF_DOMAIN
    assert evidence["canonical_product_detail_url_evidence"] is True
    assert evidence["explicit_purchase_evidence"] is True
    assert evidence["page_subject_domain"] == OUT_OF_DOMAIN
