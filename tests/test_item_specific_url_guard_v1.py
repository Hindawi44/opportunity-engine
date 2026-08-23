from __future__ import annotations

from opportunity_engine.discovery.exa_shadow_page_verification import _looks_item_specific_url


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
