import json

import pytest

from opportunity_engine.ods.daily_pipeline import AutomatedDailyPipeline, DailyPipelineConfig
from opportunity_engine.ods.konkurskupp import KonkurskuppFeedClient, parse_konkurskupp_feed


PAYLOAD = {
    "items": [
        {
            "id": "asset-1",
            "title": "Butikkinnredning fra konkursbo",
            "description": "Hyller og salgsdisk",
            "url": "https://auction.example/items/1",
            "price_nok": 12000,
            "city": "Trondheim",
            "ends_at": "2026-08-01T18:00:00+02:00",
            "mva_status": "excluded",
        },
        {
            "id": "asset-2",
            "title": "Kontorstoler",
            "url": "https://auction.example/items/2",
        },
    ]
}


def _client() -> KonkurskuppFeedClient:
    return KonkurskuppFeedClient(
        feed_url="https://feed.example/konkurskupp.json",
        token="secret",
        transport=lambda url, timeout, headers: json.dumps(PAYLOAD).encode("utf-8"),
    )


def test_authorized_feed_is_normalized() -> None:
    documents = _client().fetch(keyword="butikk")

    assert len(documents) == 1
    assert documents[0].document_id == "konkurskupp-asset-1"
    assert documents[0].source_name == "Konkurskupp"
    assert documents[0].metadata["current_price_nok"] == 12000.0
    assert documents[0].metadata["city"] == "Trondheim"
    assert documents[0].metadata["access_mode"] == "authorized_feed"


def test_pipeline_combines_authorized_konkurskupp_feed(tmp_path) -> None:
    class EmptyAuksjonen:
        def search(self, *, keyword=None):
            return ()

    output = tmp_path / "today.json"
    result = AutomatedDailyPipeline(
        client=EmptyAuksjonen(),
        konkurskupp_client=_client(),
    ).run(DailyPipelineConfig(output_path=str(output)))

    assert result.fetched_count == 2
    assert result.source_counts == {"Auksjonen.no": 0, "Konkurskupp": 2}
    assert result.extracted_count == 2


def test_invalid_json_and_insecure_feed_are_rejected() -> None:
    with pytest.raises(ValueError):
        KonkurskuppFeedClient(feed_url="http://unsafe.example/feed")
    with pytest.raises(RuntimeError):
        parse_konkurskupp_feed("not-json")


def test_missing_or_unsafe_items_are_ignored() -> None:
    payload = {"items": [{"title": "No URL"}, {"title": "Unsafe", "url": "http://example.test"}]}
    assert parse_konkurskupp_feed(json.dumps(payload)) == ()
