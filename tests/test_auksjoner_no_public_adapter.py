import json
from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.discovery.auksjoner_no_public_adapter import (
    CURRENT_AUCTIONS_URL,
    ROBOTS_URL,
    AuksjonerNoPublicCollector,
    build_auction_url,
    is_approved_current_url,
    normalize_current_auction,
    parse_current_auction_payload,
    write_auksjoner_no_artifacts,
)

NOW = datetime(2026, 7, 30, 0, 0, tzinfo=timezone.utc)
ROBOTS = "User-agent: *\nDisallow: /account\n"


def current_html(auctions):
    payload = {
        "props": {
            "basePath": "https://www.auksjoner.no/api",
            "pageProps": {"auctions": auctions, "error": False},
        },
        "page": "/[locale]/auctions",
        "query": {"locale": "nb-NO"},
    }
    return (
        '<html><body><script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(payload)
        + "</script></body></html>"
    )


def auction_record(**overrides):
    record = {
        "auctionId": 41,
        "name": "Revehiet AS dets konkursbo - Fjellreven klær",
        "description": "Ca. 500 Fjellreven plagg, bukser og jakker selges samlet.",
        "startDate": "2026-07-20T10:00:00Z",
        "endDate": "2026-08-10T18:00:00Z",
        "buyersPremium": 20,
        "hidden": False,
        "state": {"name": "Active", "id": 2, "abbreviation": "Active"},
    }
    record.update(overrides)
    return record


def test_scope_and_auction_url_are_narrow():
    assert is_approved_current_url(CURRENT_AUCTIONS_URL)
    assert not is_approved_current_url("https://www.auksjoner.no/nb-NO/auctions/past")
    assert build_auction_url(41) == "https://www.auksjoner.no/nb-NO/auctions/41"


def test_next_data_parser_reads_current_auctions_array():
    auctions = parse_current_auction_payload(current_html([auction_record()]))

    assert len(auctions) == 1
    assert auctions[0]["auctionId"] == 41


def test_active_clothing_inventory_auction_is_top5_eligible():
    auction = normalize_current_auction(auction_record(), now=NOW)
    assert auction is not None
    payload = auction.to_dict()

    assert auction.listing_status == "ACTIVE"
    assert auction.clothing_signal is True
    assert auction.inventory_lot_signal is True
    assert auction.buyers_premium_percent == 20.0
    assert payload["top5_eligible"] is True
    assert payload["analysis_eligible"] is True
    assert payload["automatic_bid"] is False


def test_individual_clothing_auction_does_not_enter_top5():
    auction = normalize_current_auction(
        auction_record(
            name="En Fjellreven jakke",
            description="Jakke størrelse XL.",
        ),
        now=NOW,
    )
    assert auction is not None

    assert auction.listing_status == "ACTIVE"
    assert auction.clothing_signal is True
    assert auction.inventory_lot_signal is False
    assert auction.to_dict()["top5_eligible"] is False


def test_ended_or_hidden_auction_is_never_active():
    ended = normalize_current_auction(
        auction_record(
            state={"name": "Ended", "id": 5},
            endDate="2026-07-29T18:00:00Z",
        ),
        now=NOW,
    )
    hidden = normalize_current_auction(
        auction_record(hidden=True),
        now=NOW,
    )

    assert ended is not None and ended.listing_status == "NOT_ACTIVE_OR_UNVERIFIED"
    assert hidden is not None and hidden.listing_status == "NOT_ACTIVE_OR_UNVERIFIED"


def test_current_empty_market_is_successful_and_past_is_never_queried():
    calls = []
    sleeps = []
    pages = {
        ROBOTS_URL: ROBOTS,
        CURRENT_AUCTIONS_URL: current_html([]),
    }

    def fetch_text(url):
        calls.append(url)
        return pages[url]

    collection = AuksjonerNoPublicCollector(
        fetch_text=fetch_text,
        sleep_fn=sleeps.append,
        now=NOW,
    ).collect()

    assert calls == [ROBOTS_URL, CURRENT_AUCTIONS_URL]
    assert sleeps == [2.0]
    assert collection.items_received == 0
    assert collection.auctions == ()
    assert collection.inventory_opportunities == ()
    assert collection.scan_complete is True
    assert collection.errors == ()
    assert collection.to_dict()["past_page_queried"] is False


def test_collector_keeps_only_valid_current_records_and_separates_non_lots():
    pages = {
        ROBOTS_URL: ROBOTS,
        CURRENT_AUCTIONS_URL: current_html(
            [
                auction_record(),
                auction_record(
                    auctionId=42,
                    name="En Fjellreven jakke",
                    description="Jakke størrelse XL.",
                ),
                {"auctionId": "bad", "name": "Broken"},
            ]
        ),
    }
    collection = AuksjonerNoPublicCollector(
        fetch_text=lambda url: pages[url],
        sleep_fn=lambda seconds: None,
        now=NOW,
    ).collect()

    assert collection.items_received == 3
    assert len(collection.auctions) == 2
    assert [item.auction_id for item in collection.inventory_opportunities] == [41]
    assert [item.auction_id for item in collection.clothing_non_lots] == [42]
    assert collection.scan_complete is True


def test_robots_block_fails_closed_without_current_page_request():
    calls = []

    def fetch_text(url):
        calls.append(url)
        return "User-agent: *\nDisallow: /nb-NO/auctions/*\n"

    collection = AuksjonerNoPublicCollector(
        fetch_text=fetch_text,
        sleep_fn=lambda seconds: None,
        now=NOW,
    ).collect()

    assert calls == [ROBOTS_URL]
    assert collection.scan_complete is False
    assert collection.auctions == ()
    assert collection.errors[0]["stage"] == "current_auctions"


def test_artifacts_write_verified_lots_only_to_commercial_top5(tmp_path: Path):
    pages = {
        ROBOTS_URL: ROBOTS,
        CURRENT_AUCTIONS_URL: current_html(
            [
                auction_record(),
                auction_record(
                    auctionId=42,
                    name="En Fjellreven jakke",
                    description="Jakke størrelse XL.",
                ),
            ]
        ),
    }
    collection = AuksjonerNoPublicCollector(
        fetch_text=lambda url: pages[url],
        sleep_fn=lambda seconds: None,
        now=NOW,
    ).collect()
    paths = write_auksjoner_no_artifacts(collection, tmp_path)

    top5 = json.loads(paths["commercial_top5"].read_text(encoding="utf-8"))
    non_lots = json.loads(paths["non_lots"].read_text(encoding="utf-8"))
    report = json.loads(paths["report"].read_text(encoding="utf-8"))
    summary = paths["summary"].read_text(encoding="utf-8")

    assert len(top5) == 1
    assert top5[0]["auction_id"] == 41
    assert top5[0]["top5_eligible"] is True
    assert len(non_lots) == 1
    assert non_lots[0]["auction_id"] == 42
    assert report["commercial_top5_count"] == 1
    assert report["past_page_queried"] is False
    assert "Valid inventory opportunities: 1" in summary
