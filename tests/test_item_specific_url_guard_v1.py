from __future__ import annotations

from opportunity_engine.discovery.exact_lot_child_link_resolution import _classify_child_page
from opportunity_engine.discovery.exa_shadow_page_verification import (
    EXACT_LOT_CANDIDATE,
    _looks_item_specific_url,
)
from opportunity_engine.project_domain_boundary import OUT_OF_DOMAIN


def test_aggregate_lot_index_is_not_item_specific() -> None:
    assert _looks_item_specific_url("https://www.sdpie.com/lots-en-vente/") is False
    assert _looks_item_specific_url("https://example.com/lots/") is False
    assert _looks_item_specific_url("https://example.com/products/") is False


def test_nested_single_lot_detail_remains_item_specific() -> None:
    assert (
        _looks_item_specific_url(
            "https://www.sdpie.com/lots-en-vente/lot-de-vestes-et-costumes/"
        )
        is True
    )


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
