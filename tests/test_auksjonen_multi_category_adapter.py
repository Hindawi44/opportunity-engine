import json
from urllib.parse import parse_qs, urlparse

from opportunity_engine.discovery.auksjonen_multi_category_adapter import (
    APPROVED_CLOTHING_CATEGORIES,
    AuksjonenMultiCategoryCollector,
    build_category_page_endpoint,
    is_approved_category_endpoint,
    write_multi_category_artifact,
)

FAR_FUTURE_MS = 4102444800000


def raw_item(object_id: int, title: str) -> dict[str, object]:
    return {
        "address": "Testveien 1",
        "auctionId": 900000 + object_id,
        "bidCount": 0,
        "bidExpired": False,
        "bidderCount": 0,
        "buyNowPrice": None,
        "category1": 1011,
        "category2": 10110508,
        "city": "Oslo",
        "currency": "NOK",
        "currentBidAmount": 0.0,
        "endTime": FAR_FUTURE_MS,
        "mainImage": f"{object_id}.jpg",
        "objectId": object_id,
        "startPrice": 0.0,
        "status": "INPROGRESS",
        "title": title,
        "zipCode": "0001",
    }


def test_only_observed_clothing_categories_are_approved():
    assert [category.category_id for category in APPROVED_CLOTHING_CATEGORIES] == [
        "10110508",
        "90010",
    ]
    for category in APPROVED_CLOTHING_CATEGORIES:
        assert is_approved_category_endpoint(category.endpoint)
    assert not is_approved_category_endpoint(
        "https://ny.auksjonen.no/api/category-search/search"
        "?category2=12345&from=1&to=30&asc=true&orderBy=endTime"
    )


def test_secondary_category_page_endpoint_is_bounded():
    category = APPROVED_CLOTHING_CATEGORIES[1]
    url = build_category_page_endpoint(category, 31, 60)
    query = parse_qs(urlparse(url).query)

    assert query["category2"] == ["90010"]
    assert query["from"] == ["31"]
    assert query["to"] == ["60"]


def test_collector_combines_categories_and_promotes_lot(monkeypatch):
    collector = AuksjonenMultiCategoryCollector()

    def fake_fetch(url: str):
        query = parse_qs(urlparse(url).query)
        category_id = query["category2"][0]
        if category_id == "10110508":
            return {"size": 1, "items": [raw_item(1, "Jakke størrelse XL")]}
        return {
            "size": 1,
            "items": [raw_item(2, "Restlager med 120 stk arbeidsjakker")],
        }

    monkeypatch.setattr(collector, "_fetch", fake_fetch)
    result = collector.collect()
    combined = result.combined

    assert len(result.scans) == 2
    assert result.scan_complete is True
    assert combined.reported_size == 2
    assert combined.items_received == 2
    assert combined.pages_fetched == 2
    assert [item.title for item in combined.inventory_opportunities] == [
        "Restlager med 120 stk arbeidsjakker"
    ]
    assert [item.title for item in combined.individual_clothing_items] == [
        "Jakke størrelse XL"
    ]


def test_duplicate_object_is_kept_once_across_categories(monkeypatch):
    collector = AuksjonenMultiCategoryCollector()
    duplicate = raw_item(7, "Vareparti med 40 stk jakker")

    def fake_fetch(url: str):
        return {"size": 1, "items": [duplicate]}

    monkeypatch.setattr(collector, "_fetch", fake_fetch)
    result = collector.collect()

    assert len(result.combined.listings) == 1
    assert len(result.combined.inventory_opportunities) == 1


def test_category_diagnostics_are_written(tmp_path, monkeypatch):
    collector = AuksjonenMultiCategoryCollector()

    def fake_fetch(url: str):
        return {"size": 0, "items": []}

    monkeypatch.setattr(collector, "_fetch", fake_fetch)
    result = collector.collect()
    path = write_multi_category_artifact(result, tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["category_count"] == 2
    assert payload["scan_complete"] is True
    assert payload["combined"]["valid_inventory_opportunity_count"] == 0
    assert payload["paid_search_used"] is False
