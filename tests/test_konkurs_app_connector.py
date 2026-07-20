import json

import pytest

from opportunity_engine.ods.daily_pipeline import AutomatedDailyPipeline, DailyPipelineConfig
from opportunity_engine.ods.konkurs_app import KonkursAppFeedClient, parse_konkurs_app_feed


PAYLOAD = {
    "items": [
        {
            "id": "case-1",
            "company_name": "Nordbutikk AS",
            "description": "Butikkinnredning og varelager",
            "url": "https://example.test/cases/1",
            "organization_number": "999888777",
            "city": "Trondheim",
            "bankruptcy_date": "2026-07-20T08:00:00Z",
            "deadline": "2026-08-10T12:00:00+02:00",
            "price_nok": 15000,
            "mva_status": "excluded",
        },
        {
            "id": "case-2",
            "company_name": "Kontorpartner AS",
            "description": "Kontormøbler",
            "url": "https://example.test/cases/2",
        },
    ]
}


def _client() -> KonkursAppFeedClient:
    return KonkursAppFeedClient(
        feed_url="https://feed.example/konkurs-app.json",
        token="secret",
        transport=lambda url, timeout, headers: json.dumps(PAYLOAD).encode("utf-8"),
    )


def test_authorized_feed_is_normalized() -> None:
    documents = _client().fetch(keyword="butikk")

    assert len(documents) == 1
    assert documents[0].document_id == "konkurs-app-case-1"
    assert documents[0].source_name == "Konkurs.app"
    assert documents[0].source_type == "authorized_liquidation_asset"
    assert documents[0].metadata["current_price_nok"] == 15000.0
    assert documents[0].metadata["organization_number"] == "999888777"
    assert documents[0].metadata["access_mode"] == "authorized_feed"


def test_pipeline_combines_authorized_konkurs_app_feed(tmp_path) -> None:
    class EmptyAuksjonen:
        def search(self, *, keyword=None):
            return ()

    output = tmp_path / "today.json"
    result = AutomatedDailyPipeline(
        client=EmptyAuksjonen(),
        konkurs_app_client=_client(),
    ).run(DailyPipelineConfig(output_path=str(output)))

    assert result.fetched_count == 2
    assert result.extracted_count == 2
    assert result.deduplicated_count == 2
    assert result.source_counts == {"Auksjonen.no": 0, "Konkurs.app": 2}


def test_invalid_json_and_insecure_feed_are_rejected() -> None:
    with pytest.raises(ValueError):
        KonkursAppFeedClient(feed_url="http://unsafe.example/feed")
    with pytest.raises(RuntimeError):
        parse_konkurs_app_feed("not-json")


def test_missing_or_unsafe_items_are_ignored() -> None:
    payload = {
        "items": [
            {"company_name": "Missing URL"},
            {"company_name": "Unsafe", "url": "http://example.test/case"},
        ]
    }
    assert parse_konkurs_app_feed(json.dumps(payload)) == ()
