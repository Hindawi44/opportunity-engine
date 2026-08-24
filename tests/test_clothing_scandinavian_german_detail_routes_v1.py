from __future__ import annotations

from opportunity_engine.discovery.exact_lot_child_link_resolution import _classify_child_page
from opportunity_engine.discovery.exact_lot_multihop_resolution import _commercial_url_role
from opportunity_engine.discovery.exa_shadow_page_verification import (
    EXACT_LOT_CANDIDATE,
    _looks_item_specific_url,
)
from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    OUT_OF_DOMAIN,
    classify_project_domain,
)


def test_swedish_parti_numeric_route_is_item_specific() -> None:
    assert _looks_item_specific_url(
        "https://example.se/restpartier/1/20/parti/2359"
    ) is True


def test_generic_german_products_clothing_category_is_aggregate() -> None:
    assert _looks_item_specific_url(
        "https://example.de/products/bekleidung/"
    ) is False


def test_nested_german_bekleidung_route_is_category_navigation() -> None:
    assert _commercial_url_role(
        "https://example.de/products/bekleidung/herrenbekleidung/"
    ) == "CATEGORY"
    assert _commercial_url_role(
        "https://example.de/product/herbol-herren-fleece-und-sweatjacken-a-ware/"
    ) == "PRODUCT_DETAIL"


def test_swedish_labeled_quantity_and_saljas_form_strict_exact_lot() -> None:
    classification, evidence = _classify_child_page(
        title="Klänningar - restparti kläder",
        text=(
            "Restparti kläder. Pris 14 000,00 kr. Kvantitet 140. "
            "Klänningar i olika modeller säljas som ett parti."
        ),
        url="https://example.se/restpartier/1/20/parti/2359",
    )

    assert classification == EXACT_LOT_CANDIDATE
    assert evidence["project_domain"] == "CLOTHING_INVENTORY"
    assert evidence["page_subject_domain"] == "CLOTHING_INVENTORY"
    assert evidence["direct_sale_evidence"] is True
    assert evidence["price_evidence"] is True
    assert evidence["quantity_evidence"] is True
    assert evidence["item_specific_url_evidence"] is True


def test_norwegian_plagg_and_dash_bid_price_are_commercial_evidence() -> None:
    classification, evidence = _classify_child_page(
        title="Stort vareparti arbeidsklær - 137 plagg",
        text=(
            "Vareparti med arbeidsklær selges samlet. 137 plagg, nye og ubrukte. "
            "Høyeste bud 500,-. Jakker og bukser."
        ),
        url="https://example.no/auksjon/overskuddsvarer/stort-parti-arbeidsklaer/616267",
    )

    assert classification == EXACT_LOT_CANDIDATE
    assert evidence["price_evidence"] is True
    assert evidence["quantity_evidence"] is True
    assert evidence["direct_sale_evidence"] is True
    assert evidence["item_specific_url_evidence"] is True


def test_live_shaped_norwegian_naeringsmiddel_klaer_lot_is_clothing() -> None:
    classification, evidence = _classify_child_page(
        title="Stort parti helse- og næringsmiddelklær - 137 plagg",
        text=(
            "Vareparti selges samlet. 137 plagg, nye og ubrukte. "
            "Høyeste bud 500,-."
        ),
        url=(
            "https://example.no/auksjon/overskuddsvarer/"
            "Stort_parti_helse-_og_n%C3%A6ringsmiddelkl%C3%A6r_-_137_plagg/616267"
        ),
    )

    assert classification == EXACT_LOT_CANDIDATE
    assert evidence["project_domain"] == CLOTHING_INVENTORY
    assert evidence["page_subject_domain"] == CLOTHING_INVENTORY
    assert evidence["price_evidence"] is True
    assert evidence["quantity_evidence"] is True
    assert evidence["direct_sale_evidence"] is True
    assert evidence["item_specific_url_evidence"] is True


def test_confirmed_german_clothing_compounds_stay_in_clothing_domain() -> None:
    samples = (
        "Herbol Herren Fleece- und Sweatjacken A-Ware",
        "Restposten Fleecejacken A-Ware",
        "Herrenbekleidung Restposten",
    )
    for text in samples:
        assert classify_project_domain(text=text) == CLOTHING_INVENTORY


def test_german_singular_product_uses_cart_control_only_on_real_detail() -> None:
    classification, evidence = _classify_child_page(
        title="Herbol Herren Fleece- und Sweatjacken A-Ware",
        text=(
            "Restposten A-Ware. Verfügbare Menge 32 Stk. Preis 2,88€. "
            "In den Warenkorb."
        ),
        url="https://example.de/product/herbol-herren-fleece-und-sweatjacken-a-ware/",
    )

    assert classification == EXACT_LOT_CANDIDATE
    assert evidence["project_domain"] == CLOTHING_INVENTORY
    assert evidence["page_subject_domain"] == CLOTHING_INVENTORY
    assert evidence["canonical_product_detail_url_evidence"] is True
    assert evidence["explicit_purchase_evidence"] is True
    assert evidence["direct_sale_evidence"] is True
    assert evidence["price_evidence"] is True
    assert evidence["quantity_evidence"] is True
    assert evidence["item_specific_url_evidence"] is True


def test_cart_text_on_generic_products_category_cannot_create_exact_lot() -> None:
    classification, evidence = _classify_child_page(
        title="Bekleidung Großhandel",
        text=(
            "Restposten Bekleidung. 32 Stk. 2,88€. In den Warenkorb. "
            "Viele Jacken, Hosen und weitere Produkte."
        ),
        url="https://example.de/products/bekleidung/",
    )

    assert classification != EXACT_LOT_CANDIDATE
    assert evidence["item_specific_url_evidence"] is False
    assert evidence["canonical_product_detail_url_evidence"] is False
    assert evidence["explicit_purchase_evidence"] is False


def test_mixed_general_merchandise_subject_stays_out_of_domain() -> None:
    classification, evidence = _classify_child_page(
        title="Blandet varelager med elektro, klær, verktøy og husholdning",
        text=(
            "Vareparti selges samlet. 137 plagg og varer. Høyeste bud 500,-. "
            "Klær, elektro, verktøy og husholdning."
        ),
        url="https://example.no/auksjon/overskuddsvarer/blandet-elektro-klaer-verktoy/616999",
    )

    assert classification == OUT_OF_DOMAIN
    assert evidence["mixed_general_merchandise_subject_evidence"] is True
    assert evidence["page_subject_domain"] == OUT_OF_DOMAIN
    assert evidence["project_domain"] == OUT_OF_DOMAIN
