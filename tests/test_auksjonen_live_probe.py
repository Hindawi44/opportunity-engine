from pathlib import Path

import pytest

from opportunity_engine.discovery.auksjonen_live_probe import (
    AuksjonenLiveProbeConfig,
    AuksjonenLiveProbeResult,
    extract_candidate_objects,
    is_approved_entry_url,
    json_shape,
    redact_url,
    should_capture_response,
    write_probe_artifacts,
)


def test_entry_url_accepts_old_and_new_hosts_only():
    assert is_approved_entry_url(
        "https://auksjonen.no/auksjoner/overskudd_klaer"
    )
    assert is_approved_entry_url(
        "https://ny.auksjonen.no/auksjoner/overskudd_klaer"
    )
    assert not is_approved_entry_url(
        "https://evil.example/auksjoner/overskudd_klaer"
    )
    assert not is_approved_entry_url(
        "https://ny.auksjonen.no/auksjoner/varelager"
    )


def test_config_rejects_unapproved_scope_and_unbounded_values():
    with pytest.raises(ValueError):
        AuksjonenLiveProbeConfig(entry_url="https://example.com/")
    with pytest.raises(ValueError):
        AuksjonenLiveProbeConfig(delay_seconds=1.0)
    with pytest.raises(ValueError):
        AuksjonenLiveProbeConfig(max_responses=61)


def test_response_selection_prefers_json_and_public_api_calls():
    assert should_capture_response(
        "https://api.example.no/search",
        content_type="application/json",
        resource_type="fetch",
    )
    assert should_capture_response(
        "https://ny.auksjonen.no/api/auctions",
        content_type="text/plain",
        resource_type="xhr",
    )
    assert not should_capture_response(
        "https://ny.auksjonen.no/assets/app.js",
        content_type="application/javascript",
        resource_type="script",
    )


def test_sensitive_query_values_are_redacted():
    redacted = redact_url(
        "https://api.example.no/search?q=klaer&token=secret&api_key=abc"
    )
    assert "q=klaer" in redacted
    assert "secret" not in redacted
    assert "abc" not in redacted
    assert "%3Credacted%3E" in redacted


def test_nested_candidate_objects_are_extracted_without_fixed_schema():
    payload = {
        "data": {
            "search": {
                "items": [
                    {
                        "auctionId": 12345,
                        "auctionTitle": "Vareparti med arbeidsklær",
                        "auctionStatus": "ACTIVE",
                        "currentBid": 4200,
                        "city": "Trondheim",
                        "endsAt": "2026-08-01T18:00:00Z",
                        "publicUrl": "https://ny.auksjonen.no/auction/12345",
                    },
                    {
                        "auctionId": 12345,
                        "auctionTitle": "Vareparti med arbeidsklær",
                        "publicUrl": "https://ny.auksjonen.no/auction/12345",
                    },
                ]
            }
        }
    }

    candidates = extract_candidate_objects(payload)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["title"] == "Vareparti med arbeidsklær"
    assert candidate["id"] == "12345"
    assert candidate["status"] == "ACTIVE"
    assert candidate["price"] == "4200"
    assert candidate["location"] == "Trondheim"


def test_json_shape_reports_object_and_array_structure():
    assert json_shape({"data": [], "meta": {}}) == {
        "type": "object",
        "keys": ["data", "meta"],
    }
    shape = json_shape([{"id": 1, "title": "A"}])
    assert shape["type"] == "array"
    assert shape["length"] == 1
    assert shape["first_item_keys"] == ["id", "title"]


def test_artifacts_state_no_paid_search_or_commercial_action(tmp_path: Path):
    result = AuksjonenLiveProbeResult(
        captured_at="2026-07-29T18:00:00+00:00",
        entry_url="https://ny.auksjonen.no/auksjoner/overskudd_klaer",
        final_url="https://ny.auksjonen.no/auksjoner/overskudd_klaer",
        pages_visited=1,
        network_responses=({
            "url": "https://api.example.no/auctions",
            "status": 200,
        },),
        candidate_objects=({
            "title": "Arbeidsklær",
            "id": "1",
        },),
        dom_links=(),
        errors=(),
    )

    paths = write_probe_artifacts(result, tmp_path)
    report = paths["report"].read_text(encoding="utf-8")
    summary = paths["summary"].read_text(encoding="utf-8")

    assert '"paid_search_used": false' in report
    assert '"openai_api_used": false' in report
    assert '"automatic_bid": false' in report
    assert "Paid Brave/OpenAI calls: 0" in summary
