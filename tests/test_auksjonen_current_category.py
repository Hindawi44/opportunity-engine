import pytest

from opportunity_engine.discovery.auksjonen_current_category import (
    DEFAULT_AUKSJONEN_CLOTHING_CATEGORY_URL,
    AuksjonenCurrentCategoryAugmentedProvider,
    AuksjonenCurrentCategoryCollector,
    AuksjonenCurrentCategoryConfig,
    is_approved_auksjonen_clothing_category_url,
    normalize_category_cards,
)
from opportunity_engine.discovery.clothing_inventory_search import DiscoveryQuery
from opportunity_engine.discovery.search_provider import SearchHit


def _query(text="vareparti klær site:auksjonen.no"):
    return DiscoveryQuery(
        "sale-03",
        "AUCTION",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        text,
    )


class StubProvider:
    name = "Stub Search"

    def __init__(self, results):
        self.results = results
        self.calls = []

    def search(self, query, *, count=10):
        self.calls.append((query, count))
        return tuple(self.results.get(query, ()))[:count]


def test_category_scope_is_one_exact_public_clothing_page():
    assert is_approved_auksjonen_clothing_category_url(
        DEFAULT_AUKSJONEN_CLOTHING_CATEGORY_URL
    ) is True
    assert is_approved_auksjonen_clothing_category_url(
        "https://www.auksjonen.no/auksjoner/overskudd_klaer/"
    ) is True
    assert is_approved_auksjonen_clothing_category_url(
        "https://auksjonen.no/auksjoner/overskudd_klaer?ordering=nyeste"
    ) is False
    assert is_approved_auksjonen_clothing_category_url(
        "https://auksjonen.no/auksjoner/alle"
    ) is False
    assert is_approved_auksjonen_clothing_category_url(
        "https://example.no/auksjoner/overskudd_klaer"
    ) is False


def test_config_enforces_small_volume_and_delay():
    with pytest.raises(ValueError, match="max_listings"):
        AuksjonenCurrentCategoryConfig(max_listings=11)
    with pytest.raises(ValueError, match="delay_seconds"):
        AuksjonenCurrentCategoryConfig(delay_seconds=1.9)
    with pytest.raises(ValueError, match="approved"):
        AuksjonenCurrentCategoryConfig(
            category_url="https://auksjonen.no/auksjoner/alle"
        )


def test_normalize_cards_accepts_specific_items_and_deduplicates():
    rows = [
        {
            "title": "20 stk arbeidsklær og regnklær",
            "url": "https://www.auksjonen.no/auksjon/torget/Arbeidsklaer/600001?utm_source=test",
            "description": "Uten minstepris. Budfrist i morgen.",
        },
        {
            "title": "20 stk arbeidsklær og regnklær",
            "url": "https://auksjonen.no/auksjon/torget/Arbeidsklaer/600001",
            "description": "Duplikat.",
        },
        {
            "title": "Generisk kategori",
            "url": "https://auksjonen.no/auksjoner/overskudd_klaer",
            "description": "Kategori.",
        },
        {
            "title": "Ekstern side",
            "url": "https://example.no/auksjon/torget/Test/600002",
            "description": "Klær til salgs.",
        },
    ]

    hits = normalize_category_cards(rows, query=_query())

    assert len(hits) == 1
    assert hits[0].url == "https://auksjonen.no/auksjon/torget/Arbeidsklaer/600001"
    assert hits[0].provider == "Auksjonen Current Category"
    assert "Klær/Arbeidsklær" in hits[0].description


def test_collector_returns_bounded_hits_and_diagnostics():
    def loader(url):
        assert url == DEFAULT_AUKSJONEN_CLOTHING_CATEGORY_URL
        return url, [
            {
                "title": "Parti med nye arbeidsjakker",
                "url": "https://auksjonen.no/auksjon/torget/Arbeidsjakker/600101",
                "description": "50 jakker. Auksjon pågår.",
            },
            {
                "title": "Parti med arbeidsbukser",
                "url": "https://auksjonen.no/auksjon/torget/Arbeidsbukser/600102",
                "description": "80 bukser. Auksjon pågår.",
            },
        ]

    collector = AuksjonenCurrentCategoryCollector(
        AuksjonenCurrentCategoryConfig(max_listings=1),
        category_page_loader=loader,
    )
    collection = collector.collect(query=_query())
    diagnostics = collection.diagnostics()

    assert len(collection.hits) == 1
    assert collection.pages_visited == 1
    assert collection.rows_seen == 2
    assert diagnostics["specific_item_hits"] == 1
    assert diagnostics["used"] is True
    assert diagnostics["automatic_bid"] is False
    assert diagnostics["automatic_purchase_decision"] is False


def test_collector_fails_closed_when_category_redirects():
    collector = AuksjonenCurrentCategoryCollector(
        category_page_loader=lambda url: (
            "https://auksjonen.no/auksjoner/alle",
            [],
        )
    )

    collection = collector.collect(query=_query())

    assert collection.hits == ()
    assert collection.pages_visited == 1
    assert collection.errors
    assert "redirected outside" in collection.errors[0]["error"]
    assert collection.diagnostics()["final_url"] == "https://auksjonen.no/auksjoner/alle"


def test_augmented_provider_prioritizes_current_hits_only_for_target_query():
    target = _query().query
    other = "konkurs klesbutikk site:forvalt.no"
    old = SearchHit(
        "Gammelt klesparti",
        "https://auksjonen.no/auksjon/torget/Gammelt/500001",
        "Klær til salgs.",
        "Stub Search",
    )
    current = SearchHit(
        "Nytt klesparti",
        "https://auksjonen.no/auksjon/torget/Nytt/600001",
        "Klær til salgs.",
        "Auksjonen Current Category",
    )
    duplicate = SearchHit(
        "Duplikat",
        "https://www.auksjonen.no/auksjon/torget/Nytt/600001?x=1",
        "Klær til salgs.",
        "Stub Search",
    )
    base = StubProvider({
        target: (old, duplicate),
        other: (SearchHit("Forvalt", "https://forvalt.no/Konkurs/Firmadetaljer/1/2"),),
    })
    provider = AuksjonenCurrentCategoryAugmentedProvider(
        base,
        target_query=target,
        current_hits=(current,),
    )

    target_hits = provider.search(target, count=2)
    other_hits = provider.search(other, count=2)

    assert [hit.title for hit in target_hits] == ["Nytt klesparti", "Gammelt klesparti"]
    assert [hit.title for hit in other_hits] == ["Forvalt"]
    assert base.calls == [(target, 2), (other, 2)]


def test_augmented_provider_requires_target_query():
    with pytest.raises(ValueError, match="target_query"):
        AuksjonenCurrentCategoryAugmentedProvider(
            StubProvider({}),
            target_query=" ",
            current_hits=(),
        )
