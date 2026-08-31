from opportunity_engine.discovery.exa_shadow_page_verification import (
    EXACT_LOT_CANDIDATE,
    _looks_item_specific_url,
)
from opportunity_engine.discovery.exact_lot_child_link_resolution import _classify_child_page


def test_partijhandel_numeric_record_route_is_item_specific_only_for_detail_shape() -> None:
    detail = "https://example.test/partijhandel/kleding/baby-en-kinder-badkleding/37526"
    category = "https://example.test/partijhandel/kleding"
    pagination = "https://example.test/partijhandel/kleding/2"
    unrelated = "https://example.test/archive/kleding/baby-en-kinder-badkleding/37526"

    assert _looks_item_specific_url(detail) is True
    assert _looks_item_specific_url(category) is False
    assert _looks_item_specific_url(pagination) is False
    assert _looks_item_specific_url(unrelated) is False


def test_misdecoded_cp1252_euro_price_recovers_strict_exact_lot() -> None:
    url = "https://example.test/partijhandel/kleding/baby-en-kinder-badkleding/37526"
    title = "Kleding partij - baby en kinder badkleding"
    text = (
        "Voor verkoop. Kleding voorraad: baby en kinder badkleding \x80 2000 exclusief BTW. "
        "Omschrijving 500 stuks baby en kinder badkleding diverse merken."
    )

    classification, evidence = _classify_child_page(title=title, text=text, url=url)

    assert classification == EXACT_LOT_CANDIDATE
    assert evidence["item_specific_url_evidence"] is True
    assert evidence["price_evidence"] is True
    assert evidence["quantity_evidence"] is True
    assert evidence["project_domain"] == "CLOTHING_INVENTORY"


def test_misdecoded_euro_normalization_does_not_create_price_without_number() -> None:
    url = "https://example.test/partijhandel/kleding/baby-en-kinder-badkleding/37526"
    classification, evidence = _classify_child_page(
        title="Kleding partij - baby en kinder badkleding",
        text="Voor verkoop. Kleding restpartij 500 stuks baby badkleding. Los teken \x80 zonder prijs.",
        url=url,
    )
    assert evidence["price_evidence"] is False
    assert classification != EXACT_LOT_CANDIDATE
