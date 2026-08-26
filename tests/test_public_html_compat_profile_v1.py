from __future__ import annotations

from opportunity_engine.discovery import keyword_shadow_verification as verification


class _FakeResponse:
    def __init__(self, *, status_code: int, body: bytes = b"", content_type: str = "text/html"):
        self.status_code = status_code
        self.url = "https://example.com/products/lot-500-pcs/12345"
        self.headers = {"Content-Type": content_type}
        self.encoding = "utf-8"
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def iter_content(self, chunk_size: int = 16384):
        del chunk_size
        if self._body:
            yield self._body


def test_public_html_compat_profile_keeps_one_request_and_no_bypass_state(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return _FakeResponse(status_code=403)

    monkeypatch.setattr(verification.requests, "get", fake_get)

    result = verification.fetch_public_page(
        "https://example.com/products/lot-500-pcs/12345"
    )

    assert result.ok is False
    assert result.status_code == 403
    assert result.error == "HTTP_403"
    assert len(calls) == 1

    _, kwargs = calls[0]
    headers = kwargs["headers"]
    assert "Mozilla/5.0" in headers["User-Agent"]
    assert "OpportunityEngine/1.0" in headers["User-Agent"]
    assert "text/html" in headers["Accept"]
    assert headers["Accept-Language"] == "en-US,en;q=0.8"
    assert "Cookie" not in headers
    assert "Authorization" not in headers
    assert "cookies" not in kwargs
    assert "auth" not in kwargs
    assert "proxies" not in kwargs
    assert kwargs["allow_redirects"] is True
    assert kwargs["stream"] is True


def test_public_html_compat_profile_preserves_successful_html_parsing(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return _FakeResponse(
            status_code=200,
            body=b"<html><head><title>Lot 500 pcs</title></head><body>Stock for sale EUR 5, 500 pcs</body></html>",
        )

    monkeypatch.setattr(verification.requests, "get", fake_get)

    result = verification.fetch_public_page(
        "https://example.com/products/lot-500-pcs/12345"
    )

    assert result.ok is True
    assert result.status_code == 200
    assert result.title == "Lot 500 pcs"
    assert "Stock for sale EUR 5, 500 pcs" in result.text
    assert result.error is None
    assert len(calls) == 1
