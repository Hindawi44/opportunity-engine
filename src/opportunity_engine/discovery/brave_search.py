"""Brave Web Search API adapter for Discovery Engine V1.1."""
from __future__ import annotations

import json
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


class BraveSearchProvider:
    """Search the public web through Brave and normalize ordinary web results."""

    name = "Brave Search"

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 20.0,
        transport: Transport | None = None,
    ) -> None:
        token = api_key.strip()
        if not token:
            raise ValueError("Brave API key is required")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._api_key = token
        self._timeout = timeout
        self._transport = transport or _default_transport

    def search(self, query: str, *, count: int = 10) -> list[SearchHit]:
        clean_query = " ".join(query.split())
        if not clean_query:
            raise ValueError("search query must not be empty")
        if not 1 <= count <= 20:
            raise ValueError("count must be between 1 and 20")

        params = urlencode({
            "q": clean_query,
            "count": count,
            "country": "NO",
            "search_lang": "no",
            "ui_lang": "nb-NO",
            "safesearch": "moderate",
        })
        request = Request(
            f"{BRAVE_WEB_SEARCH_ENDPOINT}?{params}",
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self._api_key,
                "User-Agent": "OpportunityEngine/Discovery-1.1",
            },
        )
        try:
            raw = self._transport(request, self._timeout)
            payload = json.loads(raw.decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"Brave Search returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError("Brave Search request failed") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Brave Search returned invalid JSON") from exc

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
