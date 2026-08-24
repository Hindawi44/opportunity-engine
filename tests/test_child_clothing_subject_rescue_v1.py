from __future__ import annotations

import pytest

from opportunity_engine.discovery.exact_lot_child_link_resolution import _classify_child_page
from opportunity_engine.discovery.exa_shadow_page_verification import EXACT_LOT_CANDIDATE
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY, OUT_OF_DOMAIN


_LIVE_PROVEN_CLOTHING_CHILDREN = (
    "https://salzmann-restwaren.de/product/damen-unterwaesche-mix-versch-modelle-a-b-ware/",
    "https://salzmann-restwaren.de/product/gemischter-posten-damenbekleidung-mit-verschiedenen-modellen-a-ware/",
    "https://salzmann-restwaren.de/product/herbol-damen-arbeits-bundhosen-malerhosen-versch-groessen-a-ware/",
    "https://salzmann-restwaren.de/product/damen-stretch-longtops-tunika-tops-farb-mix-a-ware/",
    "https://salzmann-restwaren.de/product/poloshirts-mix-kurzarm-langarm-verschiedene-marken-farben-a-ware/",
    "https://salzmann-restwaren.de/product/bonita-damen-steppwesten-braun-westen-versch-groessen-uebergangswesten/",
    "https://salzmann-restwaren.de/product/herbol-arbeitsmantel-arbeitskittel-malerjacke-mit-taschen-versch-groessen-a-ware/",
    "https://vinqa-grossiste.com/products/box-shorts-de-sport-de-marque",
    "https://vinqa-grossiste.com/products/box-shorts-de-marque-x20",
    "https://friptadium.com/products/blazers-femme-au-kilo",
    "https://vinqa-grossiste.com/products/box-short-de-bain-mix-marques",
    "https://vinqa-grossiste.com/products/mix-10kg-sweats-pulls-de-marque",
)


@pytest.mark.parametrize("url", _LIVE_PROVEN_CLOTHING_CHILDREN)
def test_live_clothing_product_subjects_do_not_false_negative_out_of_domain(url: str) -> None:
    classification, evidence = _classify_child_page(
        title="",
        text="Stock available for sale. Price 500 EUR. Quantity 20 pcs. Add to cart.",
        url=url,
    )

    assert evidence["page_subject_domain"] == CLOTHING_INVENTORY
    assert evidence["project_domain"] == CLOTHING_INVENTORY
    assert evidence["domain_evidence"] is True
    assert classification == EXACT_LOT_CANDIDATE


@pytest.mark.parametrize(
    "url,title",
    (
        ("https://www.sdpie.com/lots-en-vente/lot-de-papeterie/", "Lot de papeterie"),
        ("https://www.sdpie.com/lots-en-vente/lot-de-peinture/", "Lot de peinture"),
        ("https://www.sdpie.com/lots-en-vente/lot-de-montre-pour-homme-gto-time/", "Montre pour homme"),
        ("https://www.sdpie.com/lots-en-vente/lot-de-miroirs/", "Lot de miroirs"),
        ("https://www.sdpie.com/lots-en-vente/lot-distributeur-de-savon-automatique/", "Distributeur de savon"),
    ),
)
def test_non_clothing_children_still_fail_closed_even_with_clothing_site_chrome(
    url: str,
    title: str,
) -> None:
    classification, evidence = _classify_child_page(
        title=title,
        text="Vêtements stock available for sale. Price 500 EUR. Quantity 20 pcs.",
        url=url,
    )

    assert evidence["full_page_project_domain"] == CLOTHING_INVENTORY
    assert evidence["page_subject_domain"] == OUT_OF_DOMAIN
    assert evidence["project_domain"] == OUT_OF_DOMAIN
    assert evidence["domain_evidence"] is False
    assert classification == OUT_OF_DOMAIN
