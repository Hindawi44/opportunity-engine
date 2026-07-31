from opportunity_engine.discovery.auksjonen_current_category import (
    AuksjonenCurrentCategoryCollector,
    is_approved_auksjonen_clothing_category_url,
    normalize_category_cards,
)
from opportunity_engine.discovery.clothing_inventory_search import DiscoveryQuery


def _query() -> DiscoveryQuery:
    return DiscoveryQuery(
        "sale-03",
        "AUCTION",
        "SALE_INTENT",
        "SEWING_MACHINERY",
        "industrisymaskiner tekstilbedrift auksjon site:auksjonen.no",
    )


def test_new_frontend_category_redirect_is_approved_but_remains_route_bounded() -> None:
    assert is_approved_auksjonen_clothing_category_url(
        "https://ny.auksjonen.no/auksjoner/overskudd_klaer"
    ) is True
    assert is_approved_auksjonen_clothing_category_url(
        "https://ny.auksjonen.no/auksjoner/alle"
    ) is False
    assert is_approved_auksjonen_clothing_category_url(
        "https://ny.auksjonen.no/auksjoner/overskudd_klaer?sort=new"
    ) is False


def test_new_frontend_item_links_are_canonicalized_before_existing_hard_gates() -> None:
    hits = normalize_category_cards(
        [
            {
                "title": "Industrisymaskiner fra tekstilbedrift",
                "url": "https://ny.auksjonen.no/auksjon/torget/Industrisymaskiner/700001",
                "description": "Auksjon med flere industrisymaskiner.",
            }
        ],
        query=_query(),
    )

    assert len(hits) == 1
    assert hits[0].url == (
        "https://auksjonen.no/auksjon/torget/Industrisymaskiner/700001"
    )


def test_collector_accepts_only_the_known_new_frontend_redirect() -> None:
    collector = AuksjonenCurrentCategoryCollector(
        category_page_loader=lambda url: (
            "https://ny.auksjonen.no/auksjoner/overskudd_klaer",
            [
                {
                    "title": "Parti med industrisymaskiner",
                    "url": "https://ny.auksjonen.no/auksjon/torget/Symaskiner/700002",
                    "description": "Aktiv auksjon.",
                }
            ],
        )
    )

    collection = collector.collect(query=_query())

    assert collection.errors == ()
    assert len(collection.hits) == 1
    assert collection.diagnostics()["specific_item_hits"] == 1
    assert collection.final_url == (
        "https://ny.auksjonen.no/auksjoner/overskudd_klaer"
    )
