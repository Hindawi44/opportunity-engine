from __future__ import annotations

from opportunity_engine.discovery import exa_shadow_page_verification as verification
from opportunity_engine.discovery.direct_exact_lot_parser_recovery_v1 import (
    install_direct_exact_lot_parser_recovery_v1,
)


install_direct_exact_lot_parser_recovery_v1()


def test_descriptive_listing_lot_route_is_item_specific_with_all_strict_evidence() -> None:
    for url in (
        "https://example.no/listing/vareparti-med-klaer/",
        "https://example.no/listing/vareparti-med-klaer-2/",
    ):
        classification, evidence = verification._classify_page(
            title="Vareparti med klær",
            text=(
                "Vareparti med klær til salgs. Lager 500 stk. "
                "Pris 10 000 NOK. Tilgjengelig for kjøp."
            ),
            url=url,
        )

        assert classification == verification.EXACT_LOT_CANDIDATE
        assert evidence["item_specific_url_evidence"] is True
        assert evidence["inventory_evidence"] is True
        assert evidence["direct_sale_evidence"] is True
        assert evidence["price_evidence"] is True
        assert evidence["quantity_evidence"] is True
        assert evidence["domain_evidence"] is True


def test_listing_container_does_not_make_generic_slug_item_specific() -> None:
    urls = (
        "https://example.no/listing/klaer/",
        "https://example.no/listing/vareparti/",
        "https://example.no/listing/summer-fashion/",
        "https://example.no/category/listing/vareparti-med-klaer/",
    )

    for url in urls:
        assert verification._looks_item_specific_url(url) is False


def test_listing_route_still_requires_full_exact_lot_evidence() -> None:
    classification, evidence = verification._classify_page(
        title="Vareparti med klær",
        text="Vareparti med klær til salgs. Lager 500 stk. Tilgjengelig nå.",
        url="https://example.no/listing/vareparti-med-klaer-2/",
    )

    assert evidence["item_specific_url_evidence"] is True
    assert evidence["price_evidence"] is False
    assert classification != verification.EXACT_LOT_CANDIDATE
