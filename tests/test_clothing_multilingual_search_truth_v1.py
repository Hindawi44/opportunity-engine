from __future__ import annotations

from opportunity_engine.discovery.exa_shadow_page_verification import (
    EXACT_LOT_CANDIDATE,
    _classify_page,
    _looks_item_specific_url,
)
from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    FABRIC_PROCUREMENT,
    OUT_OF_DOMAIN,
    classify_project_domain,
)


def test_dutch_clothing_compound_titles_and_urls_stay_in_clothing_domain() -> None:
    samples = (
        "Kledingpartij herenkleding PME Legend Vanguard Cast Iron",
        "Partij dameskleding en herenkleding 2174 stuks",
        "Partij kinderkleding Vingino 8000 stuks",
        "Merkkleding voorraad te koop",
    )
    for text in samples:
        assert classify_project_domain(text=text) == CLOTHING_INVENTORY


def test_generic_dutch_non_clothing_partij_stays_out_of_domain() -> None:
    assert classify_project_domain(text="Partij elektronica 500 stuks te koop") == OUT_OF_DOMAIN


def test_dutch_fabric_commercial_language_still_wins_for_fabric() -> None:
    assert (
        classify_project_domain(text="Restpartij stoffen groothandel, stoffen per meter")
        == FABRIC_PROCUREMENT
    )


def test_numeric_marketplace_detail_is_item_specific_but_search_root_is_not() -> None:
    assert (
        _looks_item_specific_url(
            "https://example.fr/acheter/c-940122-destockage-de-jeans-femme-tiffosi.html"
        )
        is True
    )
    assert (
        _looks_item_specific_url(
            "https://example.fr/acheter/recherche-fournisseur-0-vetements.html"
        )
        is False
    )


def test_explicit_acheter_au_vendeur_can_prove_strict_french_clothing_lot() -> None:
    classification, evidence = _classify_page(
        title="Déstockage de jeans femme Tiffosi",
        text=(
            "Stock de vêtements en déstockage. 120 pièces. Prix 8 EUR la pièce. "
            "Bonne affaire : acheter au vendeur."
        ),
        url="https://example.fr/acheter/c-940122-destockage-de-jeans-femme-tiffosi.html",
    )

    assert classification == EXACT_LOT_CANDIDATE
    assert evidence["project_domain"] == CLOTHING_INVENTORY
    assert evidence["inventory_evidence"] is True
    assert evidence["direct_sale_evidence"] is True
    assert evidence["price_evidence"] is True
    assert evidence["quantity_evidence"] is True
    assert evidence["item_specific_url_evidence"] is True


def test_grossiste_role_alone_is_not_direct_sale() -> None:
    classification, evidence = _classify_page(
        title="Grossiste vêtements",
        text="Stock de vêtements pour professionnels. 120 pièces. Prix 8 EUR.",
        url="https://example.fr/catalogue-vetements",
    )

    assert classification != EXACT_LOT_CANDIDATE
    assert evidence["direct_sale_evidence"] is False
