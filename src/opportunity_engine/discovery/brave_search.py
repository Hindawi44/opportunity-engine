"""Brave Web Search API adapter for Discovery Engine."""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from opportunity_engine.discovery.search_provider import SearchHit

BRAVE_WEB_SEARCH_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
Transport = Callable[[Request, float], bytes]


def _default_transport(request: Request, timeout: float) -> bytes:
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS API endpoint
        return response.read()


def _http_error_message(exc: HTTPError) -> str:
    """Return a useful provider error without exposing credentials."""
    try:
        body = exc.read().decode("utf-8", errors="replace").strip()
    except Exception:  # pragma: no cover - defensive fallback
        body = ""
    body = " ".join(body.split())[:500]
    suffix = f": {body}" if body else ""
    return f"Brave Search returned HTTP {exc.code}{suffix}"


class BraveSearchProvider:
    """Search the public web through Brave and normalize ordinary web results."""

    name = "Brave Search"

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 20.0,
        transport: Transport | None = None,
        max_retries: int = 3,
        retry_base_seconds: float = 1.0,
    ) -> None:
        token = api_key.strip()
        if not token:
            raise ValueError("Brave API key is required")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_retries < 0:
            raise ValueError("max_retries must not be negative")
        if retry_base_seconds < 0:
            raise ValueError("retry_base_seconds must not be negative")
        self._api_key = token
        self._timeout = timeout
        self._transport = transport or _default_transport
        self._max_retries = max_retries
        self._retry_base_seconds = retry_base_seconds

    def search(self, query: str, *, count: int = 10) -> list[SearchHit]:
        clean_query = " ".join(query.split())
        if not clean_query:
            raise ValueError("search query must not be empty")
        if not 1 <= count <= 20:
            raise ValueError("count must be between 1 and 20")

        # ui_lang is intentionally omitted. Brave validates it against a strict
        # locale enum, and unsupported Norwegian locale variants return HTTP 422.
        params = urlencode({
            "q": clean_query,
            "count": count,
            "country": "NO",
            "search_lang": "no",
            "safesearch": "moderate",
        })
        request = Request(
            f"{BRAVE_WEB_SEARCH_ENDPOINT}?{params}",
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self._api_key,
                "User-Agent": "OpportunityEngine/Discovery-1.4.1",
            },
        )

        raw: bytes | None = None
        for attempt in range(self._max_retries + 1):
            try:
                raw = self._transport(request, self._timeout)
                break
            except HTTPError as exc:
                if exc.code == 429 and attempt < self._max_retries:
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    try:
                        wait_seconds = float(retry_after) if retry_after else self._retry_base_seconds * (2**attempt)
                    except (TypeError, ValueError):
                        wait_seconds = self._retry_base_seconds * (2**attempt)
                    time.sleep(max(0.0, wait_seconds))
                    continue
                raise RuntimeError(_http_error_message(exc)) from exc
            except URLError as exc:
                raise RuntimeError(f"Brave Search request failed: {exc.reason}") from exc

        if raw is None:  # pragma: no cover - loop guarantees a result or exception
            raise RuntimeError("Brave Search returned no response")

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            preview = raw[:300].decode("utf-8", errors="replace")
            raise RuntimeError(f"Brave Search returned invalid JSON: {preview}") from exc

        return _parse_hits(payload)


def _parse_hits(payload: Any) -> list[SearchHit]:
    if not isinstance(payload, dict):
        return []
    web = payload.get("web")
    results = web.get("results") if isinstance(web, dict) else None
    if not isinstance(results, list):
        return []

    hits: list[SearchHit] = []
    seen_urls: set[str] = set()
    for item in results:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        description = str(item.get("description") or "").strip()
        if not title or not url.startswith("https://") or url in seen_urls:
            continue
        seen_urls.add(url)
        hits.append(SearchHit(title=title, url=url, description=description, provider="Brave Search"))
    return hits
