import base64
import json
from pathlib import Path

import pytest
import requests

from opportunity_engine.discovery.finn_email_intake import (
    FinnEmailMessage,
    collect_finn_saved_search_messages,
    run_finn_email_intake,
)
from scripts.run_finn_email_intake import (
    _json_object,
    fetch_finn_messages_from_gmail,
    link_auksjonen_channels,
)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, raw_message: bytes):
        encoded = base64.urlsafe_b64encode(raw_message).decode("ascii").rstrip("=")
        self.responses = [
            FakeResponse({"access_token": "access-token"}),
            FakeResponse({"messages": [{"id": "gmail-message-1"}]}),
            FakeResponse({"raw": encoded}),
        ]
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.responses.pop(0)


def _error_response(payload: object, *, status_code: int = 400) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.url = "https://oauth2.googleapis.com/token"
    response.headers["Content-Type"] = "application/json"
    response._content = json.dumps(payload).encode("utf-8")
    return response


def test_gmail_api_fetch_is_bounded_and_read_only():
    raw = (
        "From: FINN <agent@finn.no>\n"
        "Subject: Nye annonser: vareparti klær\n"
        "Date: Tue, 04 Aug 2026 18:00:00 +0000\n"
        "Message-ID: <gmail-fixture@example.test>\n"
        "Content-Type: text/plain; charset=UTF-8\n\n"
        "Parti arbeidsklær\nhttps://www.finn.no/471396147\n"
    ).encode()
    session = FakeSession(raw)

    messages = fetch_finn_messages_from_gmail(
        "client-id",
        "client-secret",
        "refresh-token",
        query='from:agent@finn.no subject:"Nye annonser:" newer_than:7d',
        max_messages=20,
        session=session,
    )

    assert len(messages) == 1
    assert messages[0].sender == "FINN <agent@finn.no>"
    assert messages[0].subject == "Nye annonser: vareparti klær"
    assert [call[0] for call in session.calls] == ["POST", "GET", "GET"]
    token_call = session.calls[0]
    assert token_call[2]["data"]["grant_type"] == "refresh_token"
    list_call = session.calls[1]
    assert list_call[2]["params"]["maxResults"] == 20
    assert list_call[2]["headers"]["Authorization"] == "Bearer access-token"
    raw_call = session.calls[2]
    assert raw_call[2]["params"] == {"format": "raw"}


def test_gmail_api_rejects_unbounded_message_count():
    with pytest.raises(ValueError, match="between 1 and 50"):
        fetch_finn_messages_from_gmail(
            "client-id",
            "client-secret",
            "refresh-token",
            max_messages=51,
            session=FakeSession(b"unused"),
        )


def test_oauth_failure_exposes_only_provider_error_code():
    response = _error_response({
        "error": "invalid_grant",
        "error_description": "sensitive provider detail must not be logged",
    })

    with pytest.raises(RuntimeError) as captured:
        _json_object(response, label="Gmail OAuth token endpoint")

    assert str(captured.value) == (
        "Gmail OAuth token endpoint rejected the request: invalid_grant"
    )
    assert "sensitive provider detail" not in str(captured.value)


def test_non_json_oauth_failure_exposes_only_http_status():
    response = requests.Response()
    response.status_code = 400
    response.url = "https://oauth2.googleapis.com/token"
    response._content = b"not-json-and-never-logged"

    with pytest.raises(RuntimeError) as captured:
        _json_object(response, label="Gmail OAuth token endpoint")

    assert str(captured.value) == (
        "Gmail OAuth token endpoint rejected the request: http_400"
    )
    assert "not-json-and-never-logged" not in str(captured.value)


def test_exact_auksjonen_seller_and_title_aliases_one_opportunity(tmp_path: Path):
    finn_url = "https://www.finn.no/471396147"
    title = "Parti Björnkläder arbeidsklær og varselklær"
    message = FinnEmailMessage(
        sender="FINN <agent@finn.no>",
        subject="Nye annonser: vareparti klær",
        body=(
            f"[{title}]({finn_url})\n"
            "Sem\n"
            "Auksjonen.No AS\n"
        ),
        received_at="2026-08-04T18:00:00+00:00",
        message_id="<auksjonen-channel@example.test>",
    )
    result = run_finn_email_intake(
        collect_finn_saved_search_messages([message])
    )
    report_path = tmp_path / "auksjonen-live-clothing-listings.json"
    report_path.write_text(
        json.dumps({
            "scan_complete": True,
            "errors": [],
            "listings": [{
                "title": title,
                "opportunity_identity": "auksjonen-auction:85260",
                "inventory_lot_signal": True,
                "listing_status": "ACTIVE",
            }],
        }),
        encoding="utf-8",
    )

    linked = link_auksjonen_channels(result, [message], report_path)

    assert linked == 1
    candidate = result["all_discovered_candidates"][0]
    assert candidate["opportunity_identity"] == "auksjonen-auction:85260"
    assert candidate["cross_channel_link"]["sale_channel"] == "Auksjonen.no"
    assert candidate["source_capture"][0]["related_sale_channel"] == "Auksjonen.no"
    assert result["search_run_report"]["auksjonen_cross_channel_links"] == 1


def test_non_auksjonen_seller_is_not_aliased(tmp_path: Path):
    finn_url = "https://www.finn.no/471396148"
    title = "Parti arbeidsklær"
    message = FinnEmailMessage(
        sender="FINN <agent@finn.no>",
        subject="Nye annonser: vareparti klær",
        body=f"[{title}]({finn_url})\nPrivat selger\n",
        message_id="<private-channel@example.test>",
    )
    result = run_finn_email_intake(
        collect_finn_saved_search_messages([message])
    )
    original_identity = result["all_discovered_candidates"][0]["opportunity_identity"]
    report_path = tmp_path / "auksjonen-live-clothing-listings.json"
    report_path.write_text(
        json.dumps({
            "listings": [{
                "title": title,
                "opportunity_identity": "auksjonen-auction:999",
                "inventory_lot_signal": True,
            }],
        }),
        encoding="utf-8",
    )

    linked = link_auksjonen_channels(result, [message], report_path)

    assert linked == 0
    assert result["all_discovered_candidates"][0]["opportunity_identity"] == original_identity
