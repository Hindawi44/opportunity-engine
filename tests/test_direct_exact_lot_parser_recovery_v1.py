from __future__ import annotations

from opportunity_engine.discovery import exa_shadow_page_verification as verification
from opportunity_engine.discovery.direct_exact_lot_parser_recovery_v1 import (
    install_direct_exact_lot_parser_recovery_v1,
)


install_direct_exact_lot_parser_recovery_v1()


def test_european_number_then_euro_symbol_is_direct_price_evidence() -> None:
    classification, evidence = verification._classify_page(
        title=(
            "306,50 € Vêtements de marque mixtes d'été Lot n° 5 "
            "115 pièces, prix unitaire 2,66 €"
        ),
        text=(
            "Stock de vêtements disponible en vente pour grossistes. "
            "Quantité 115 pièces."
        ),
        url=(
            "https://stocklots24.fr/30650-%E2%82%AC-vetements-de-marque-mixtes-"
            "lot-n-5-115-pieces-prix-unitaire-266-%E2%82%AC/10804676"
        ),
    )

    assert classification == verification.EXACT_LOT_CANDIDATE
    assert evidence["price_evidence"] is True
    assert evidence["quantity_evidence"] is True
    assert evidence["item_specific_url_evidence"] is True
    assert evidence["domain_evidence"] is True


def test_lot_intent_slug_followed_by_numeric_record_id_is_item_specific() -> None:
    assert verification._looks_item_specific_url(
        "https://www.partijhandelaren.nl/partijhandel/kleding/"
        "restpartij-131-nieuwe-t-shirts-76-stanleystella-complete-partij/37463"
    ) is True
    assert verification._looks_item_specific_url(
        "https://www.partijhandelaren.nl/partijhandel/kleding/"
        "partij-adidas-heren-en-damesbovenkleding-64-stuks/37427"
    ) is True


def test_bare_category_followed_by_numeric_id_stays_aggregate() -> None:
    assert (
        verification._looks_item_specific_url(
            "https://www.partijhandelaren.nl/partijhandel/kleding/43"
        )
        is False
    )

    classification, evidence = verification._classify_page(
        title="Kleding - PartijHandelaren.nl",
        text=(
            "Stock kleding te koop. Voorraad 200 stuks. Prijs 5,00 € per stuk."
        ),
        url="https://www.partijhandelaren.nl/partijhandel/kleding/43",
    )
    assert classification != verification.EXACT_LOT_CANDIDATE
    assert evidence["item_specific_url_evidence"] is False


def test_bare_year_in_slug_is_not_lot_intent_for_numeric_tail() -> None:
    assert (
        verification._looks_item_specific_url(
            "https://example.com/kleding/summer-sale-2026/12345"
        )
        is False
    )


def test_existing_currency_prefix_price_form_still_works() -> None:
    classification, evidence = verification._classify_page(
        title="Restpartij kleding",
        text="Stock kleding te koop. 80 stuks. € 4 per stuk.",
        url="https://example.com/lot/restpartij-kleding-80-stuks",
    )

    assert classification == verification.EXACT_LOT_CANDIDATE
    assert evidence["price_evidence"] is True
