"""Offline evidence joins: no network, paid API, seller action or database mutation."""
from copy import deepcopy

import pytest

from scripts.link_event_hunter_auction_evidence import (
    link_existing_auctions, render_linked_arabic,
)
from tests.test_event_first_hunter_pilot import source_report
from scripts.run_event_first_hunter_pilot import build_event_report


def event_report():
    return build_event_report(source_report())


def brief(*rows):
    return {"generated_at": "2026-09-19T09:00:00Z", "current_direct_opportunities": list(rows)}


def auction(**overrides):
    row = {
        "organisation_number": "123456789",
        "market_code": "NO",
        "source_url": "https://www.auksjonen.no/auksjon/torget/Tekstil_lot/632173",
        "title": "Textile stock",
        "opportunity_identity": "auction:632173",
    }
    row.update(overrides)
    return row


def test_exact_number_only_creates_unverified_auction_investigation():
    before = event_report()
    linked = link_existing_auctions(before, brief(auction()))
    item = linked["events"][0]
    assert linked["related_auction_lead_count"] == 1
    assert item["related_auction_leads"][0]["source_url"].endswith("632173")
    assert item["related_auction_leads"][0]["seller_identity_verified"] is False
    assert item["relation_evidence"] == "EXACT_REPORTED_ORGANISATION_NUMBER_UNVERIFIED_ASSOCIATION"
    assert item["inventory_verified"] is False
    assert item["inventory_link"] is None
    assert linked["verified_inventory_links"] == 0
    assert linked["paid_search_requests"] == linked["openai_requests"] == 0
    assert linked["automatic_purchase"] is False
    assert before["events"][0].get("related_auction_leads") is None  # No mutation.
    assert "لا يثبت علاقة البائع" in render_linked_arabic(linked)


def test_does_not_join_similar_names_different_numbers_or_other_markets():
    report = link_existing_auctions(event_report(), brief(
        auction(organisation_number="987654321", title="Eksempel Tekstil AS"),
        auction(market_code="SE"),
        auction(source_url="https://www.auksjonen.no/auksjon/torget/Tekstil_lot/632173?utm=1"),
        auction(source_url="https://www.some-store.example/products/123"),
        auction(source_url="https://www.auksjonen.no/prosjekt/12"),
    ))
    assert report["related_auction_lead_count"] == 0
    assert report["ignored_unmatched_or_unqualified_record_count"] == 4


def test_identical_lots_deduplicated_and_bounded():
    rows = [auction(), auction(), auction(source_url="https://www.auksjonen.no/auksjon/torget/Another_lot/632174"),
            auction(source_url="https://www.auksjonen.no/auksjon/torget/Third_lot/632175")]
    linked = link_existing_auctions(event_report(), brief(*rows), max_lots_per_event=2)
    assert linked["related_auction_lead_count"] == 2
    assert linked["events"][0]["unshown_related_auction_count"] == 1


def test_missing_brief_records_fails_closed_not_false_zero():
    with pytest.raises(ValueError, match="lacks current_direct_opportunities"):
        link_existing_auctions(event_report(), {})
    with pytest.raises(ValueError):
        link_existing_auctions({"schema_version": "other"}, brief())


def test_forged_event_source_fails_closed():
    raw = deepcopy(event_report())
    raw["events"][0]["official_source_url"] = "https://fake.example/company/123456789"
    with pytest.raises(ValueError, match="official company provenance"):
        link_existing_auctions(raw, brief(auction()))
