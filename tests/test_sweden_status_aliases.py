from opportunity_engine.discovery.clothing_inventory_search import (
    ENDED,
    DiscoveryQuery,
    classify_search_hit,
)
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.sweden_clothing_inventory import (
    SwedenLocalizedSearchProvider,
)


class StaticProvider:
    name = "static"

    def __init__(self, hit: SearchHit) -> None:
        self.hit = hit

    def search(self, query: str, *, count: int = 10):
        return [self.hit]


def _query() -> DiscoveryQuery:
    return DiscoveryQuery(
        "se-status",
        "AUCTION",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        "site:psauction.se/item/view kläder parti",
    )


def test_avslutad_search_snippet_maps_to_ended_before_page_verification():
    provider = SwedenLocalizedSearchProvider(
        StaticProvider(
            SearchHit(
                title="Parti med 180 par nya skor",
                url="https://psauction.se/item/view/1448337/parti-med-180-par-nya-skor",
                description="Avyttring · Såld · Avslutad · Parti med skor.",
                provider="Static",
            )
        )
    )

    localized = provider.search(_query().query)[0]
    observation = classify_search_hit(localized, _query())

    assert "avsluttet" in localized.description
    assert "solgt" in localized.description
    assert observation.listing_status == ENDED


def test_auction_ending_phrase_without_ended_word_is_not_marked_ended():
    provider = SwedenLocalizedSearchProvider(
        StaticProvider(
            SearchHit(
                title="Parti med kläder, ca 100 plagg",
                url="https://psauction.se/item/view/1560018/parti-med-klader",
                description="Auktionen avslutas 2026-08-04. Nuvarande bud 800 SEK.",
                provider="Static",
            )
        )
    )

    observation = classify_search_hit(provider.search(_query().query)[0], _query())

    assert observation.listing_status != ENDED
