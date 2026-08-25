from opportunity_engine.discovery.exa_shadow_page_verification import (
    EXACT_LOT_CANDIDATE,
    _classify_page,
)


DETAIL = "https://example.test/stock/donna/stock-motivi/"


def test_explicit_italian_order_intent_can_complete_existing_strict_exact_lot_evidence() -> None:
    classification, evidence = _classify_page(
        title="Stock abbigliamento donna Motivi",
        text=(
            "Stock abbigliamento donna. Per info liste e ordini contattaci. "
            "Disponibilità 800 pezzi. Prezzo 17 euro al pezzo."
        ),
        url=DETAIL,
    )

    assert classification == EXACT_LOT_CANDIDATE
    assert evidence["direct_sale_evidence"] is True
    assert evidence["inventory_evidence"] is True
    assert evidence["price_evidence"] is True
    assert evidence["quantity_evidence"] is True
    assert evidence["item_specific_url_evidence"] is True


def test_italian_order_intent_alone_never_qualifies_exact_lot() -> None:
    classification, evidence = _classify_page(
        title="Stock abbigliamento donna",
        text="Per info liste e ordini contattaci.",
        url=DETAIL,
    )

    assert classification != EXACT_LOT_CANDIDATE
    assert evidence["direct_sale_evidence"] is True
    assert evidence["price_evidence"] is False
    assert evidence["quantity_evidence"] is False


def test_italian_order_intent_still_fails_without_price() -> None:
    classification, evidence = _classify_page(
        title="Stock abbigliamento donna",
        text="Stock abbigliamento donna. Per info liste e ordini. Disponibilità 800 pezzi.",
        url=DETAIL,
    )

    assert classification != EXACT_LOT_CANDIDATE
    assert evidence["direct_sale_evidence"] is True
    assert evidence["quantity_evidence"] is True
    assert evidence["price_evidence"] is False
