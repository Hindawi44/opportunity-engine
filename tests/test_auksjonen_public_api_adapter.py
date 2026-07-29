from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.discovery.auksjonen_public_api_adapter import (
    AuksjonenLiveClothingCollection,
    AuksjonenLiveClothingListing,
    build_public_item_url,
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


def test_live_api_item_becomes_active_public_listing():
    listing = normalize_public_api_item(live_item(), now=NOW)

    assert listing is not None
    assert listing.title == "2026 Ny Klim jakke, large"
    assert listing.listing_status == "ACTIVE"
    assert listing.current_bid_nok == 250.0
    assert listing.city == "Åmli"
    assert listing.url.endswith("/2026_Ny_Klim_jakke_large/609462")
    assert listing.inventory_lot_signal is False


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


def test_inventory_lot_signal_is_preserved_without_inventing_quantity():
    listing = normalize_public_api_item(
        live_item(title="Vareparti med arbeidsklær samlet"),
        now=NOW,
    )
    assert listing is not None
    assert listing.inventory_lot_signal is True


def test_artifacts_contain_real_listing_fields_and_no_paid_calls(tmp_path: Path):
    listing = AuksjonenLiveClothingListing(
        title="Fxr jakke snøscooter, strl XL",
        url=(
            "https://ny.auksjonen.no/auksjon/torget/"
            "Fxr_jakke_sn%C3%B8scooter_strl_XL/609460"
        ),
        auction_id=888269,
        object_id=609460,
        status="INPROGRESS",
        listing_status="ACTIVE",
        current_bid_nok=0.0,
        buy_now_price_nok=None,
        start_price_nok=0.0,
        bid_count=0,
        bidder_count=0,
        city="Åmli",
        zip_code="4865",
        address=None,
        ends_at="2026-08-02T10:00:00+00:00",
        main_image="609460.jpg",
        inventory_lot_signal=False,
    )
    collection = AuksjonenLiveClothingCollection(
        captured_at="2026-07-29T18:00:00+00:00",
        endpoint=(
            "https://ny.auksjonen.no/api/category-search/search"
            "?category2=10110508&from=1&to=30&asc=true&orderBy=endTime"
        ),
        reported_size=67,
        items_received=30,
        listings=(listing,),
    )

    paths = write_live_clothing_artifacts(collection, tmp_path)
    report = paths["report"].read_text(encoding="utf-8")
    top5 = paths["top5"].read_text(encoding="utf-8")

    assert '"active_clothing_count": 1' in report
    assert '"paid_search_used": false' in report
    assert '"openai_api_used": false' in report
    assert "Fxr jakke snøscooter" in top5
    assert "609460" in top5
