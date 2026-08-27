"""Brave Web Search API adapter for Discovery Engine."""
from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from datetime import date
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from opportunity_engine.discovery.search_provider import SearchHit

BRAVE_WEB_SEARCH_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
Transport = Callable[[Request, float], bytes]
_FRESHNESS_PRESETS = frozenset({"pd", "pw", "pm", "py"})
_CUSTOM_FRESHNESS = re.compile(r"^(\d{4}-\d{2}-\d{2})to(\d{4}-\d{2}-\d{2})$")
_COUNTRY_CODE = re.compile(r"^[A-Z]{2}$")
# A Brave monthly/account usage-limit response cannot recover inside the same
# process. Once the live transport receives HTTP 402, stop making subsequent
# network calls and let downstream paths fail fast instead of multiplying waste.
_USAGE_LIMIT_CIRCUIT_OPEN = False
_USAGE_LIMIT_CIRCUIT_MESSAGE = (
    "Brave Search usage limit circuit open after HTTP 402; "
    "subsequent requests skipped for this process"
)
# Exact PS Auction item-ID lookups are verification/status queries, not fresh
# discovery. Applying a page-age filter can hide the historical item page that
# proves an already-discovered candidate is ENDED, leaving stale lots unresolved.
_PSAUCTION_EXACT_ITEM_STATUS_LOOKUP = re.compile(
    r'^site:psauction\.se/item/view\s+"\d+"$',
    re.I,
)


def _default_transport(request: Request, timeout: float) -> bytes:
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS API endpoint
        return response.read()


def _open_usage_limit_circuit() -> None:
    global _USAGE_LIMIT_CIRCUIT_OPEN
    _USAGE_LIMIT_CIRCUIT_OPEN = True


def _reset_usage_limit_circuit_for_tests() -> None:
    """Reset process-local provider state for deterministic isolated tests."""
    global _USAGE_LIMIT_CIRCUIT_OPEN
    _USAGE_LIMIT_CIRCUIT_OPEN = False


def _http_error_message(exc: HTTPError) -> str:
    """Return a useful provider error without exposing credentials."""
    try:
        body = exc.read().decode("utf-8", errors="replace").strip()
    except Exception:  # pragma: no cover - defensive fallback
        body = ""
    body = " ".join(body.split())[:500]
    suffix = f": {body}" if body else ""
    return f"Brave Search returned HTTP {exc.code}{suffix}"


def _validated_freshness(value: str | None) -> str | None:
    """Validate Brave freshness presets or an inclusive custom date range."""
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if cleaned in _FRESHNESS_PRESETS:
        return cleaned
    match = _CUSTOM_FRESHNESS.fullmatch(cleaned)
    if not match:
        raise ValueError(
            "freshness must be pd, pw, pm, py, or YYYY-MM-DDtoYYYY-MM-DD"
        )
    start = date.fromisoformat(match.group(1))
    end = date.fromisoformat(match.group(2))
    if start > end:
        raise ValueError("freshness start date must not be after end date")
    return cleaned


def _validated_country(value: str) -> str:
    cleaned = value.strip().upper()
    if _COUNTRY_CODE.fullmatch(cleaned) is None:
        raise ValueError("country must be a two-letter code")
    return cleaned


def _combined_description(item: dict[str, Any]) -> str:
    """Combine the main snippet with bounded, deduplicated extra snippets."""
    values: list[str] = []
    description = item.get("description")
    if isinstance(description, str):
        values.append(description)
    extra = item.get("extra_snippets")
    if isinstance(extra, list):
        values.extend(value for value in extra[:5] if isinstance(value, str))

    snippets: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(value.split())
        marker = cleaned.casefold()
        if not cleaned or marker in seen:
            continue
        seen.add(marker)
        snippets.append(cleaned)
    return " | ".join(snippets)[:6000]


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
        freshness: str | None = None,
        extra_snippets: bool = False,
        operators: bool = True,
        country: str = "NO",
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
        self._uses_default_transport = transport is None
        self._transport = transport or _default_transport
        self._max_retries = max_retries
        self._retry_base_seconds = retry_base_seconds
        self._freshness = _validated_freshness(freshness)
        self._extra_snippets = bool(extra_snippets)
        self._operators = bool(operators)
        self._country = _validated_country(country)

    def search(self, query: str, *, count: int = 10) -> list[SearchHit]:
        clean_query = " ".join(query.split())
        if not clean_query:
            raise ValueError("search query must not be empty")
        if not 1 <= count <= 20:
            raise ValueError("count must be between 1 and 20")
        if self._uses_default_transport and _USAGE_LIMIT_CIRCUIT_OPEN:
            raise RuntimeError(_USAGE_LIMIT_CIRCUIT_MESSAGE)

        # Market intent exists in the selected market query terms. Brave's
        # language parameters are strict enums, so geographic targeting remains
        # explicit while language is inferred from each query.
        params: dict[str, str | int] = {
            "q": clean_query,
            "count": count,
            "country": self._country,
            "safesearch": "moderate",
            "result_filter": "web",
            "operators": "true" if self._operators else "false",
        }
        effective_freshness = self._freshness
        if _PSAUCTION_EXACT_ITEM_STATUS_LOOKUP.fullmatch(clean_query):
            effective_freshness = None
        if effective_freshness:
            params["freshness"] = effective_freshness
        if self._extra_snippets:
            params["extra_snippets"] = "true"

        request = Request(
            f"{BRAVE_WEB_SEARCH_ENDPOINT}?{urlencode(params)}",
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self._api_key,
                "User-Agent": "OpportunityEngine/Discovery-1.4.3",
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
                        wait_seconds = (
                            float(retry_after)
                            if retry_after
                            else self._retry_base_seconds * (2**attempt)
                        )
                    except (TypeError, ValueError):
                        wait_seconds = self._retry_base_seconds * (2**attempt)
                    time.sleep(max(0.0, wait_seconds))
                    continue
                if exc.code == 402 and self._uses_default_transport:
                    _open_usage_limit_circuit()
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
        description = _combined_description(item)
        if not title or not url.startswith("https://") or url in seen_urls:
            continue
        seen_urls.add(url)
        hits.append(
            SearchHit(
                title=title,
                url=url,
                description=description,
                provider="Brave Search",
            )
        )
    return hits
