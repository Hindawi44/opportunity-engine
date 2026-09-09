from opportunity_engine.discovery.clothing_inventory_search import (
    ITEM_LISTING,
    REJECTED_NOISE,
    STRONG_LEAD_REQUIRES_VERIFICATION,
    DiscoveryQuery,
    classify_search_hit,
)
from opportunity_engine.discovery.search_provider import SearchHit


def _bulk_query() -> DiscoveryQuery:
    return DiscoveryQuery(
        "finn-jeans-regression",
        "LARGE_LOT_SALE",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:finn.no "partisalg" jeans',
    )


def test_stardust_100_jeans_finn_listing_is_retained_as_clothing_bulk_lot():
    result = classify_search_hit(
        SearchHit(
            "PARTISALG 100 STK ASSORTERTE JEANS FRA STARDUST",
            "https://www.finn.no/recommerce/forsale/item/450273961",
            "",
            "Regression fixture from a real FINN listing",
        ),
        _bulk_query(),
    )

    assert result.state == STRONG_LEAD_REQUIRES_VERIFICATION
    assert result.scenario == "LARGE_LOT_SALE"
    assert result.page_role_hint == ITEM_LISTING
    assert result.identity_stable is True
    assert result.opportunity_identity == "url-id:450273961"
    assert "jeans" in result.signals
    assert "partisalg" in result.signals


def test_plain_single_jeans_listing_still_does_not_become_bulk_inventory():
    result = classify_search_hit(
        SearchHit(
            "Jeans størrelse 32 selges",
            "https://www.finn.no/recommerce/forsale/item/450273962",
            "Brukt jeans i god stand.",
            "Regression fixture",
        ),
        _bulk_query(),
    )

    assert result.state == REJECTED_NOISE


def test_partisalg_without_clothing_scope_still_does_not_become_clothing_inventory():
    result = classify_search_hit(
        SearchHit(
            "PARTISALG +/- 150 STK HVITVINSGLASS",
            "https://www.finn.no/recommerce/forsale/item/450273963",
            "Selges samlet.",
            "Regression fixture",
        ),
        _bulk_query(),
    )

    assert result.state == REJECTED_NOISE
