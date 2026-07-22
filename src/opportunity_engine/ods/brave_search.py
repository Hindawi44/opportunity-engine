"""Brave Search API client for authorized web discovery.

The client performs bounded searches, preserves missing values as ``None``, and
never logs or serializes the API key.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

JsonTransport = Callable[[str, float, dict[str, str]], bytes]


def _default_transport(url: str, timeout: float, headers: dict[str, str]) -> bytes:
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed official API
            return response.read()
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise RuntimeError("Brave Search authentication failed") from exc
        if exc.code == 429:
            raise RuntimeError("Brave Search rate limit reached") from exc
        raise RuntimeError(f"Brave Search returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Brave Search request failed: {exc.reason}") from exc


@dataclass(frozen=True)
class BraveSearchClient:
    api_key: str
    base_url: str = "https://api.search.brave.com/res/v1/web/search"
    timeout: float = 20.0
    transport: JsonTransport = _default_transport

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("api_key must not be empty")
        if not self.base_url.startswith("https://"):
            raise ValueError("base_url must use HTTPS")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
            "User-Agent": "Opportunity-Engine/1.0 (authorized-search)",
        }

    def search(self, query: str, *, count: int = 10, country: str = "NO", search_lang: str = "no") -> list[dict[str, object]]:
        query = query.strip()
        if not query:
            raise ValueError("query must not be empty")
        if not 1 <= count <= 20:
            raise ValueError("count must be between 1 and 20")
        params = urlencode({
            "q": query,
            "count": count,
            "country": country,
            "search_lang": search_lang,
            "safesearch": "moderate",
            "text_decorations": "false",
            "spellcheck": "true",
        })
        payload = self.transport(f"{self.base_url}?{params}", self.timeout, self.headers)
        return parse_brave_results(payload)


def parse_brave_results(payload: bytes | str) -> list[dict[str, object]]:
    try:
        decoded = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        data = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise RuntimeError("Brave Search returned invalid JSON") from exc

    web = data.get("web", {}) if isinstance(data, dict) else {}
    items = web.get("results", []) if isinstance(web, dict) else []
    if not isinstance(items, list):
        raise RuntimeError("Brave Search response does not contain web results")

    results: list[dict[str, object]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        if not title or not url.startswith(("https://", "http://")):
            continue
        results.append({
            "title": title,
            "url": url,
            "snippet": str(item.get("description") or "").strip(),
            "source": "Brave Search",
            "published_at": item.get("page_age") or None,
        })
    return results
