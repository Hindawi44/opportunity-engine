import json

import pytest

from opportunity_engine.ods.generic_authorized_feed import (
    GenericAuthorizedFeedClient,
    parse_authorized_feed,
)


def test_rejects_non_https_feed_url():
    with pytest.raises(ValueError):
        GenericAuthorizedFeedClient(
            source_name="Kommuner",
            source_type="public_auction_event_lead",
            feed_url="http://example.test/feed.json",
        )


def test_parses_and_deduplicates_authorized_feed():
    payload = {
        "items": [
            {
                "id": "abc",
                "title": "Kontormøbler fra kommune",
                "url": "https://example.no/auction/abc",
                "city": "Namsos",
                "ends_at": "2026-08-01T12:00:00Z",
            },
            {
                "id": "abc",
                "title": "Duplicate",
                "url": "https://example.no/auction/abc",
            },
        ]
    }

    documents = parse_authorized_feed(
        json.dumps(payload),
        source_name="Kommuner",
        source_type="public_auction_event_lead",
    )

    assert len(documents) == 1
    assert documents[0].source_name == "Kommuner"
    assert documents[0].source_type == "public_auction_event_lead"
    assert documents[0].metadata["city"] == "Namsos"


def test_keyword_filter_does_not_invent_missing_financial_values():
    payload = {
        "items": [
            {
                "title": "Konkursbo med varelager",
                "description": "Tekstil og butikkinnredning",
                "url": "https://example.no/estate/1",
            },
            {
                "title": "Restaurantutstyr",
                "url": "https://example.no/estate/2",
            },
        ]
    }

    documents = parse_authorized_feed(
        json.dumps(payload),
        source_name="Konkursbo",
        source_type="bankruptcy_discovery_lead",
        keyword="tekstil",
    )

    assert len(documents) == 1
    assert documents[0].metadata["current_price_nok"] is None
    assert documents[0].metadata["mva_status"] == "unknown"
