import json

import pytest

from opportunity_engine.ods.bjaroy import BjaroyFeedClient, parse_bjaroy_feed
from opportunity_engine.ods.daily_pipeline import AutomatedDailyPipeline, DailyPipelineConfig


PAYLOAD = {
    "items": [
        {
            "id": "asset-1",
            "title": "Butikkinnredning fra avvikling",
            "description": "Disker, hyller og prøverom",
            "url": "https://assets.example/bjaroy/1",
            "price_nok": 15000,
            "city": "Steinkjer",
            "deadline": "2026-08-15T12:00:00+02:00",
            "asset_type": "butikkinnredning",
            "mva_status": "excluded",
        },
        {
            "id": "asset-2",
            "title": "Kontormøbler",
            "url": "https://assets.example/bjaroy/2",
        },
    ]
}


def _client() -> BjaroyFeedClient:
    return BjaroyFeedClient(
        feed_url="https://feed.example/bjaroy.json",
        token="secret",
        transport=lambda url, timeout, headers: json.dumps(PAYLOAD).encode("utf-8"),
    )


def test_authorized_bjaroy_feed_is_normalized() -> None:
    documents = _client().fetch(keyword="butikk")

    assert len(documents) == 1
    assert documents[0].document_id == "bjaroy-asset-1"
    assert documents[0].source_name == "Bjarøy"
    assert documents[0].metadata["current_price_nok"] == 15000.0
    assert documents[0].metadata["city"] == "Steinkjer"
    assert documents[0].metadata["asset_type"] == "butikkinnredning"
    assert documents[0].metadata["access_mode"] == "authorized_feed"


def test_pipeline_combines_authorized_bjaroy_feed(tmp_path) -> None:
    class EmptyAuksjonen:
        def search(self, *, keyword=None):
            return ()

    output = tmp_path / "today.json"
    result = AutomatedDailyPipeline(
        client=EmptyAuksjonen(),
        bjaroy_client=_client(),
    ).run(DailyPipelineConfig(output_path=str(output)))

    assert result.fetched_count == 2
    assert result.source_counts == {"Auksjonen.no": 0, "Bjarøy": 2}
    assert result.extracted_count == 2
    assert result.deduplicated_count == 2


def test_invalid_json_and_insecure_feed_are_rejected() -> None:
    with pytest.raises(ValueError):
        BjaroyFeedClient(feed_url="http://unsafe.example/feed")
    with pytest.raises(RuntimeError):
        parse_bjaroy_feed("not-json")


def test_missing_or_unsafe_items_are_ignored() -> None:
    payload = {"items": [{"title": "No URL"}, {"title": "Unsafe", "url": "http://example.test"}]}
    assert parse_bjaroy_feed(json.dumps(payload)) == ()
