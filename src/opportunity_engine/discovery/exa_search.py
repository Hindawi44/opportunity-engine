"""Exa Search API adapter for bounded shadow discovery experiments."""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from opportunity_engine.discovery.search_provider import SearchHit

EXA_SEARCH_ENDPOINT = "https://api.exa.ai/search"
EXA_HIGHLIGHT_DESCRIPTION_PREFIX = "EXA_SEARCH_HIGHLIGHTS_V1::"
Transport = Callable[[Request, float], bytes]


def _default_transport(request: Request, timeout: float) -> bytes:
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS API endpoint
        return response.read()


def _http_error_message(exc: HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", errors="replace").strip()
    except Exception:  # pragma: no cover - defensive fallback
        body = ""
    body = " ".join(body.split())[:500]
    suffix = f": {body}" if body else ""
    return f"Exa Search returned HTTP {exc.code}{suffix}"


def _clean_values(values: list[str]) -> str:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        compact = " ".join(value.split())
        marker = compact.casefold()
        if not compact or marker in seen:
            continue
        seen.add(marker)
        cleaned.append(compact)
    return " | ".join(cleaned)[:6000]


def _description(item: dict[str, Any]) -> str:
    """Return search context while preserving explicit Exa-highlight provenance.

    Requested highlights are extractive provider-native source passages and are
    tagged so downstream 403 diagnostics can distinguish them from ordinary
    snippets, summaries, or synthetic test descriptions. If Exa returns no
    highlights, the historical text/summary fallback remains untagged and can
    never qualify for the 403 extractive-evidence shadow path.
    """
    highlights = item.get("highlights")
    if isinstance(highlights, list):
        highlight_text = _clean_values(
            [value for value in highlights[:5] if isinstance(value, str)]
        )
        if highlight_text:
            return f"{EXA_HIGHLIGHT_DESCRIPTION_PREFIX}{highlight_text}"

    values: list[str] = []
    text = item.get("text")
    if isinstance(text, str):
        values.append(text)
    summary = item.get("summary")
    if isinstance(summary, str):
        values.append(summary)
    return _clean_values(values)


class ExaSearchProvider:
    """Search the public web through Exa and normalize ordinary web results.

    This adapter is provider-neutral and has no authority to promote, contact,
    bid, reserve, purchase, or pay. Production activation is intentionally left
    to explicit downstream policy after shadow benchmarking.
    """

    name = "Exa"

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 20.0,
        transport: Transport | None = None,
        max_retries: int = 2,
        retry_base_seconds: float = 1.0,
    ) -> None:
        token = api_key.strip()
        if not token:
            raise ValueError("Exa API key is required")
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

        payload = {
            "query": clean_query,
            "numResults": count,
            "type": "auto",
            "contents": {"highlights": True},
        }
        request = Request(
            EXA_SEARCH_ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "x-api-key": self._api_key,
                "User-Agent": "OpportunityEngine/Exa-Shadow-1.0",
            },
            method="POST",
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
                raise RuntimeError(_http_error_message(exc)) from exc
            except URLError as exc:
                raise RuntimeError(f"Exa Search request failed: {exc.reason}") from exc

        if raw is None:  # pragma: no cover
            raise RuntimeError("Exa Search returned no response")

        try:
            response = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            preview = raw[:300].decode("utf-8", errors="replace")
            raise RuntimeError(f"Exa Search returned invalid JSON: {preview}") from exc

        return _parse_hits(response)


def _parse_hits(payload: Any) -> list[SearchHit]:
    if not isinstance(payload, dict):
        return []
    results = payload.get("results")
    if not isinstance(results, list):
        return []

    hits: list[SearchHit] = []
    seen_urls: set[str] = set()
    for item in results:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        if not title or not url.startswith("https://") or url in seen_urls:
            continue
        seen_urls.add(url)
        hits.append(
            SearchHit(
                title=title,
                url=url,
                description=_description(item),
                provider="Exa",
            )
        )
    return hits


# Keep this Exa-specific experiment isolated from provider-neutral verification.
# Importing the adapter installs only a read-only post-verification shadow: it
# never changes FETCH_FAILED, Exact-Lot, Tool Learning, Top5 or commercial state.
from opportunity_engine.discovery.exa_403_extractive_evidence_shadow_v1 import (  # noqa: E402
    install_exa_403_extractive_evidence_shadow_v1,
)

install_exa_403_extractive_evidence_shadow_v1()
