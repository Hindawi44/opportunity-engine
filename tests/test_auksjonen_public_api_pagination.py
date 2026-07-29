from urllib.parse import parse_qs, urlparse

from opportunity_engine.discovery.auksjonen_public_api_adapter import (
    AuksjonenPublicApiCollector,
    DEFAULT_PUBLIC_API_ENDPOINT,
    build_page_endpoint,
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


def test_build_page_endpoint_keeps_category_and_moves_window():
    url = build_page_endpoint(DEFAULT_PUBLIC_API_ENDPOINT, 31, 60)
    query = parse_qs(urlparse(url).query)

    assert query["category2"] == ["10110508"]
    assert query["from"] == ["31"]
    assert query["to"] == ["60"]
    assert query["orderBy"] == ["endTime"]


def test_collector_scans_all_reported_pages_and_finds_lot_on_last_page(monkeypatch):
    page_one = [raw_item(i, f"Gullkjede {i}") for i in range(1, 31)]
    page_two = [raw_item(i, f"Verktøy {i}") for i in range(31, 61)]
    page_three = [raw_item(i, f"Sykkel {i}") for i in range(61, 67)]
    page_three.append(raw_item(67, "Restlager med 120 stk arbeidsjakker"))
    payloads = [
        {"size": 67, "items": page_one},
        {"size": 67, "items": page_two},
        {"size": 67, "items": page_three},
    ]
    requested_urls: list[str] = []

    collector = AuksjonenPublicApiCollector()

    def fake_fetch(url: str):
        requested_urls.append(url)
        return payloads[len(requested_urls) - 1]

    monkeypatch.setattr(collector, "_fetch", fake_fetch)
    result = collector.collect()

    assert len(requested_urls) == 3
    assert "from=1" in requested_urls[0] and "to=30" in requested_urls[0]
    assert "from=31" in requested_urls[1] and "to=60" in requested_urls[1]
    assert "from=61" in requested_urls[2] and "to=90" in requested_urls[2]
    assert result.reported_size == 67
    assert result.items_received == 67
    assert result.pages_fetched == 3
    assert result.scan_complete is True
    assert [item.title for item in result.inventory_opportunities] == [
        "Restlager med 120 stk arbeidsjakker"
    ]


def test_collector_stops_after_short_page_when_size_is_missing(monkeypatch):
    collector = AuksjonenPublicApiCollector(page_size=30)
    requested_urls: list[str] = []

    def fake_fetch(url: str):
        requested_urls.append(url)
        return {"items": [raw_item(1, "Jakke størrelse XL")]}

    monkeypatch.setattr(collector, "_fetch", fake_fetch)
    result = collector.collect()

    assert len(requested_urls) == 1
    assert result.reported_size is None
    assert result.items_received == 1
    assert result.pages_fetched == 1
    assert result.scan_complete is True
