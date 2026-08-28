import json
from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.discovery.auksjonen_public_api_adapter import (
    AuksjonenLiveClothingCollection,
    AuksjonenLiveClothingListing,
    build_public_item_url,
    has_inventory_lot_signal,
    is_approved_public_api_endpoint,
    normalize_public_api_item,
    slugify_title,
    write_live_clothing_artifacts,
)

NOW = datetime(2026, 7, 29, 18, 0, tzinfo=timezone.utc)
FUTURE_MS = 1785691200000


def live_item(**overrides):
    item = {
        "address": "Engenes 2",
        "auctionId": 888362,
        "auctionTypeLabel": "Auksjon",
        "bidCount": 1,
        "bidExpired": False,
        "bidderCount": 1,
        "buyNowPrice": None,
        "category1": 1011,
        "category2": 10110508,
        "category3": None,
        "city": "Åmli",
        "currency": "NOK",
        "currentBidAmount": 250.0,
        "endTime": FUTURE_MS,
        "mainImage": "609462_image.jpg",
        "objectId": 609462,
        "startPrice": 0.0,
        "status": "INPROGRESS",
        "title": "2026 Ny Klim jakke, large",
        "zipCode": "4865",
    }
    item.update(overrides)
    return item


def listing(*, title: str, object_id: int, inventory_lot_signal: bool):
    return AuksjonenLiveClothingListing(
        title=title,
        url=build_public_item_url(title, object_id),
        auction_id=888000 + object_id,
        object_id=object_id,
        status="INPROGRESS",
        listing_status="ACTIVE",
        current_bid_nok=250.0,
        buy_now_price_nok=None,
        start_price_nok=0.0,
        bid_count=1,
        bidder_count=1,
        city="Åmli",
        zip_code="4865",
        address=None,
        ends_at="2026-08-02T10:00:00+00:00",
        main_image=f"{object_id}.jpg",
        inventory_lot_signal=inventory_lot_signal,
    )


def test_approved_endpoint_is_exact_public_clothing_api():
    assert is_approved_public_api_endpoint(
        "https://ny.auksjonen.no/api/category-search/search?category2=10110508&from=1&to=30"
    )
    assert not is_approved_public_api_endpoint(
        "https://evil.example/api/category-search/search?category2=10110508"
    )
    assert not is_approved_public_api_endpoint(
        "https://ny.auksjonen.no/api/category-search/search?category2=90010"
    )


def test_public_slug_and_url_match_observed_live_route():
    assert slugify_title("Fxr jakke snøscooter, strl XL") == (
        "Fxr_jakke_sn%C3%B8scooter_strl_XL"
    )
    assert build_public_item_url(
        "Fxr jakke snøscooter, strl XL",
        609460,
    ) == (
        "https://ny.auksjonen.no/auksjon/torget/"
        "Fxr_jakke_sn%C3%B8scooter_strl_XL/609460"
    )


def test_live_api_item_becomes_active_public_diagnostic_item():
    normalized = normalize_public_api_item(live_item(), now=NOW)

    assert normalized is not None
    assert normalized.title == "2026 Ny Klim jakke, large"
    assert normalized.listing_status == "ACTIVE"
    assert normalized.current_bid_nok == 250.0
    assert normalized.city == "Åmli"
    assert normalized.url.endswith("/2026_Ny_Klim_jakke_large/609462")
    assert normalized.inventory_lot_signal is False


def test_non_clothing_and_ended_items_are_rejected():
    assert normalize_public_api_item(
        live_item(title="Gullkjede i 21k gull"),
        now=NOW,
    ) is None
    assert normalize_public_api_item(
        live_item(status="ENDED"),
        now=NOW,
    ) is None
    assert normalize_public_api_item(
        live_item(bidExpired=True),
        now=NOW,
    ) is None
    assert normalize_public_api_item(
        live_item(endTime=NOW.timestamp() * 1000 - 1),
        now=NOW,
    ) is None


def test_inventory_lot_signal_requires_explicit_multi_item_evidence():
    assert has_inventory_lot_signal("Vareparti med arbeidsklær samlet")
    assert has_inventory_lot_signal("Restlager: 25 stk jakker")
    assert has_inventory_lot_signal("Flere plagg og bukser")
    assert has_inventory_lot_signal(
        "Blåkläder, Jallas, Sievi - Veil. 817.000,- 461 artikler"
    )
    assert not has_inventory_lot_signal("Fxr jakke snøscooter, strl XL")
    assert not has_inventory_lot_signal("2026 Ny Klim jakke, large")


def test_workwear_category_is_page_native_clothing_evidence_for_brand_only_lot():
    title = "Blåkläder, Jallas, Sievi - Veil. 817.000,- 461 artikler"

    assert normalize_public_api_item(live_item(title=title), now=NOW) is None

    normalized = normalize_public_api_item(
        live_item(title=title, category2=90010),
        now=NOW,
    )
    assert normalized is not None
    assert normalized.title == title
    assert normalized.inventory_lot_signal is True


def test_inventory_lot_signal_is_preserved_without_inventing_quantity():
    normalized = normalize_public_api_item(
        live_item(title="Vareparti med arbeidsklær samlet"),
        now=NOW,
    )
    assert normalized is not None
    assert normalized.inventory_lot_signal is True


def test_collection_separates_opportunities_from_individual_items():
    individual = listing(
        title="Fxr jakke snøscooter, strl XL",
        object_id=609460,
        inventory_lot_signal=False,
    )
    lot = listing(
        title="Vareparti med 25 stk arbeidsjakker",
        object_id=609500,
        inventory_lot_signal=True,
    )
    collection = AuksjonenLiveClothingCollection(
        captured_at="2026-07-29T18:00:00+00:00",
        endpoint=(
            "https://ny.auksjonen.no/api/category-search/search"
            "?category2=10110508&from=1&to=30&asc=true&orderBy=endTime"
        ),
        reported_size=67,
        items_received=30,
        listings=(lot, individual),
    )

    assert collection.inventory_opportunities == (lot,)
    assert collection.individual_clothing_items == (individual,)
    report = collection.to_dict()
    assert report["valid_inventory_opportunity_count"] == 1
    assert report["active_individual_clothing_count"] == 1
    assert report["top5_count"] == 1


def test_individual_items_are_excluded_from_top5_and_written_separately(tmp_path: Path):
    individual = listing(
        title="Fxr jakke snøscooter, strl XL",
        object_id=609460,
        inventory_lot_signal=False,
    )
    lot = listing(
        title="Vareparti med 25 stk arbeidsjakker",
        object_id=609500,
        inventory_lot_signal=True,
    )
    collection = AuksjonenLiveClothingCollection(
        captured_at="2026-07-29T18:00:00+00:00",
        endpoint=(
            "https://ny.auksjonen.no/api/category-search/search"
            "?category2=10110508&from=1&to=30&asc=true&orderBy=endTime"
        ),
        reported_size=67,
        items_received=30,
        listings=(lot, individual),
    )

    paths = write_live_clothing_artifacts(collection, tmp_path)
    report = json.loads(paths["report"].read_text(encoding="utf-8"))
    top5 = json.loads(paths["top5"].read_text(encoding="utf-8"))
    individuals = json.loads(paths["individual_items"].read_text(encoding="utf-8"))
    summary = paths["summary"].read_text(encoding="utf-8")

    assert report["active_clothing_count"] == 2
    assert report["valid_inventory_opportunity_count"] == 1
    assert report["paid_search_used"] is False
    assert report["openai_api_used"] is False
    assert [item["title"] for item in top5] == ["Vareparti med 25 stk arbeidsjakker"]
    assert all(item["inventory_lot_signal"] is True for item in top5)
    assert [item["title"] for item in individuals] == ["Fxr jakke snøscooter, strl XL"]
    assert "Fxr jakke" not in summary
    assert "Valid inventory opportunities: 1" in summary


def test_current_three_individual_jackets_produce_empty_top5(tmp_path: Path):
    current_items = (
        listing(
            title="Fxr jakke snøscooter, strl XL",
            object_id=609460,
            inventory_lot_signal=False,
        ),
        listing(
            title="2026 Ny Klim jakke, large",
            object_id=609462,
            inventory_lot_signal=False,
        ),
        listing(
            title="Ski doo jakke, strl XL",
            object_id=609461,
            inventory_lot_signal=False,
        ),
    )
    collection = AuksjonenLiveClothingCollection(
        captured_at="2026-07-29T18:00:00+00:00",
        endpoint=(
            "https://ny.auksjonen.no/api/category-search/search"
            "?category2=10110508&from=1&to=30&asc=true&orderBy=endTime"
        ),
        reported_size=67,
        items_received=30,
        listings=current_items,
    )

    paths = write_live_clothing_artifacts(collection, tmp_path)
    assert json.loads(paths["top5"].read_text(encoding="utf-8")) == []
    individuals = json.loads(paths["individual_items"].read_text(encoding="utf-8"))
    assert len(individuals) == 3
    assert all(item["inventory_lot_signal"] is False for item in individuals)
    summary = paths["summary"].read_text(encoding="utf-8")
    assert "Valid inventory opportunities: 0" in summary
    assert "Top 5 count: 0" in summary
    assert "No valid inventory-lot opportunities found." in summary
