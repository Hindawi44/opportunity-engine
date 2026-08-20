from __future__ import annotations

import base64

import requests

from opportunity_engine.discovery import auksjonen_exact_item_verification as auksjonen_verification
from opportunity_engine.discovery import vareauksjonen_public_adapter as vareauksjonen_adapter
from scripts.run_finn_email_intake import fetch_finn_messages_from_gmail


class _AuksjonenResponse:
    def __init__(self, final_url: str, body: bytes) -> None:
        self._final_url = final_url
        self._body = body
        self.headers = {"Content-Type": "text/html; charset=utf-8"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def geturl(self) -> str:
        return self._final_url

    def read(self, amount: int | None = None) -> bytes:
        return self._body if amount is None else self._body[:amount]


class _VareauksjonenResponse:
    status = 200

    def __init__(self, body: bytes = b"<html></html>") -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._body


class _JsonResponse:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _TransientGmailSession:
    def __init__(self, raw_message: bytes) -> None:
        self._encoded = base64.urlsafe_b64encode(raw_message).decode("ascii").rstrip("=")
        self.get_calls = 0

    def post(self, url, **kwargs):
        return _JsonResponse({"access_token": "access-token"})

    def get(self, url, **kwargs):
        self.get_calls += 1
        if self.get_calls == 1:
            raise requests.ConnectionError("synthetic connection reset")
        if self.get_calls == 2:
            return _JsonResponse({"messages": [{"id": "gmail-message-1"}]})
        return _JsonResponse({"raw": self._encoded})


def test_auksjonen_accepts_official_host_redirect_with_same_object_identity(monkeypatch) -> None:
    source_url = (
        "https://ny.auksjonen.no/auksjon/torget/"
        "280_stk_GSA_jakke_oransje_art_GSA11030_str_56_60/611144"
    )
    final_url = source_url.replace("https://ny.auksjonen.no", "https://www.auksjonen.no")
    body = b"<html><body><h1>280 stk GSA jakke oransje</h1></body></html>"

    monkeypatch.setattr(
        auksjonen_verification,
        "urlopen",
        lambda request, timeout: _AuksjonenResponse(final_url, body),
    )

    decoded, redirected_to, byte_count, _digest = auksjonen_verification.fetch_auksjonen_item_page(
        source_url
    )

    assert "280 stk GSA" in decoded
    assert redirected_to == final_url
    assert byte_count == len(body)


def test_auksjonen_still_rejects_redirect_to_non_official_host(monkeypatch) -> None:
    source_url = "https://ny.auksjonen.no/auksjon/torget/Test/611144"
    final_url = "https://evil.example/auksjon/torget/Test/611144"
    body = b"<html><body>test</body></html>"

    monkeypatch.setattr(
        auksjonen_verification,
        "urlopen",
        lambda request, timeout: _AuksjonenResponse(final_url, body),
    )

    try:
        auksjonen_verification.fetch_auksjonen_item_page(source_url)
    except RuntimeError as exc:
        assert "exact public item scope" in str(exc)
    else:
        raise AssertionError("redirect to a non-official host must fail closed")


def test_vareauksjonen_percent_encodes_non_ascii_listing_path_before_request(monkeypatch) -> None:
    url = "https://www.vareauksjonen.no/Listing/Details/200001/Arbeidstøy-og-klær"
    seen_urls: list[str] = []

    def fake_urlopen(request, timeout):
        seen_urls.append(request.full_url)
        return _VareauksjonenResponse()

    monkeypatch.setattr(vareauksjonen_adapter, "urlopen", fake_urlopen)
    collector = vareauksjonen_adapter.VareauksjonenPublicCollector(
        sleep_fn=lambda seconds: None,
    )

    collector._fetch_text(url)

    assert seen_urls == [
        "https://www.vareauksjonen.no/Listing/Details/200001/Arbeidst%C3%B8y-og-kl%C3%A6r"
    ]


def test_finn_gmail_retries_one_transient_connection_failure() -> None:
    raw = (
        "From: FINN <agent@finn.no>\n"
        "Subject: Nye annonser: vareparti klær\n"
        "Date: Wed, 20 Aug 2026 05:00:00 +0000\n"
        "Message-ID: <gmail-retry@example.test>\n"
        "Content-Type: text/plain; charset=UTF-8\n\n"
        "Parti arbeidsklær\nhttps://www.finn.no/471396147\n"
    ).encode("utf-8")
    session = _TransientGmailSession(raw)

    messages = fetch_finn_messages_from_gmail(
        "client-id",
        "client-secret",
        "refresh-token",
        session=session,
    )

    assert len(messages) == 1
    assert messages[0].subject == "Nye annonser: vareparti klær"
    assert session.get_calls == 3
