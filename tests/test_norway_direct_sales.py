"""A direct item, never an event or search page, is the only reviewable sale."""
from datetime import datetime, timezone

import pytest

from scripts.run_norway_direct_sales import _candidate, discover

NOW = datetime(2026, 9, 19, 12, tzinfo=timezone.utc)
FUTURE = datetime(2026, 9, 25, 12, tzinfo=timezone.utc).timestamp() * 1000


def item(**changes):
    data = {
        "objectId": 123456, "title": "Parti kontormøbler og utstyr",
        "status": "INPROGRESS", "bidExpired": False, "endTime": FUTURE,
        "currentBidAmount": 350.0, "countryCode": "NO", "city": "Namsos",
    }
    data.update(changes)
    return data


def page(_url):
    return {"items": [item()]}


def exact(url):
    return "<html><h1>Parti kontormøbler og utstyr</h1><p>Tilstand Brukt</p></html>", url, 73, "digest"


def test_non_clothing_direct_sale_is_accepted_without_old_domain_rules():
    result = discover(page_loader=page, item_loader=exact, now=NOW)
    assert result["verified_count"] == 1
    assert result["missing_count"] == 9
    row = result["cards"][0]
    assert row["url"].endswith("/123456")
    assert row["asset_type"] == "Parti kontormøbler og utstyr"
    assert row["location"] == "Namsos"
    assert row["current_bid_nok"] == 350.0
    assert row["buy_now_nok"] is None
    assert row["status"] == "ACTIVE_VERIFIED_AT_CHECK"
    assert row["verified_at"] == NOW.isoformat()
    assert result["paid_api_requests"] == 0
    assert result["automatic_purchase"] is False


def test_expired_unlisted_and_foreign_items_never_qualify():
    for variation in ({"endTime": NOW.timestamp() * 1000}, {"status": "ENDED"},
                      {"bidExpired": True}, {"countryCode": "SE"},
                      {"objectId": None}, {"title": ""}):
        assert _candidate(item(**variation), now=NOW) is None


def test_item_page_closed_or_wrong_identity_fails_closed():
    for fetcher in (
        lambda url: ("<html><h1>Item</h1>Auksjonen er avsluttet</html>", url, 1, ""),
        lambda url: ("<html><h1>Item</h1></html>", url.replace("123456", "654321"), 1, ""),
        lambda url: ("<html>General listings only</html>", url, 1, ""),
    ):
        report = discover(page_loader=page, item_loader=fetcher, now=NOW)
        assert report["verified_count"] == 0
        assert report["failures"][0]["stage"] == "item"


def test_deduplicates_auction_identity_without_commercial_filtering():
    data = [item(), item(), item(objectId=123457, title="Elektronikk")]
    report = discover(page_loader=lambda _url: {"items": data}, item_loader=exact, now=NOW)
    assert report["distinct_active_api_candidates"] == 2
    assert report["verified_count"] == 2


def test_missing_price_and_location_are_unknown_not_guessed():
    data = item(currentBidAmount=None, city=None, countryCode="NO")
    report = discover(page_loader=lambda _url: {"items": [data]}, item_loader=exact, now=NOW)
    assert report["verified_count"] == 1
    assert report["cards"][0]["current_bid_nok"] is None
    assert report["cards"][0]["location"] is None


def test_api_failure_reports_zero_without_fake_links():
    def broken(_url):
        raise RuntimeError("Source unavailable")

    report = discover(page_loader=broken, item_loader=exact, now=NOW)
    assert report["verified_count"] == 0
    assert report["cards"] == []
    assert report["failures"][0]["stage"] == "search"


def test_bounded_inputs_and_explicit_no_purchasing():
    with pytest.raises(ValueError):
        discover(max_pages=3)
    with pytest.raises(ValueError):
        discover(max_cards=11)
    report = discover(page_loader=page, item_loader=exact, now=NOW)
    assert all(report[key] is False for key in
               ("automatic_contact", "automatic_bid", "automatic_purchase", "automatic_payment"))
    assert report["estimated_external_api_cost_usd"] == 0.0
