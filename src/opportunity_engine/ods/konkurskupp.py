"""Authorized Konkurskupp feed connector.

Konkurskupp's terms prohibit automated scraping or copying without written
consent. This connector therefore accepts only an explicitly authorized JSON
feed URL or an exported JSON payload supplied by the operator. It does not
crawl public pages, log in, or bypass access controls.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .live_data import SourceDocument
from .models import ODSRequest

JsonTransport = Callable[[str, float, dict[str, str]], bytes]


def _default_json_transport(url: str, timeout: float, headers: dict[str, str]) -> bytes:
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - operator supplied HTTPS feed
            return response.read()
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise RuntimeError("Konkurskupp feed authorization failed") from exc
        raise RuntimeError(f"Konkurskupp feed returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Konkurskupp feed request failed: {exc.reason}") from exc


@dataclass(frozen=True)
class KonkurskuppFeedClient:
    """Client for a written-permission JSON feed or official export endpoint."""

    feed_url: str
    token: str | None = None
    timeout: float = 15.0
    transport: JsonTransport = _default_json_transport

    def __post_init__(self) -> None:
        if not self.feed_url.startswith("https://"):
            raise ValueError("Konkurskupp feed_url must use HTTPS")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "Opportunity-Engine/1.0 (authorized-feed)",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def fetch(self, *, keyword: str | None = None) -> tuple[SourceDocument, ...]:
        payload = self.transport(self.feed_url, self.timeout, self.headers)
        return parse_konkurskupp_feed(payload, keyword=keyword)


@dataclass(frozen=True)
class KonkurskuppConnector:
    client: KonkurskuppFeedClient
    name: str = "konkurskupp_authorized_feed"

    def fetch(self, request: ODSRequest) -> tuple[SourceDocument, ...]:
        return self.client.fetch(keyword=request.subject)


def parse_konkurskupp_feed(payload: bytes | str, *, keyword: str | None = None) -> tuple[SourceDocument, ...]:
    try:
        decoded = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        data = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise RuntimeError("Konkurskupp feed returned invalid JSON") from exc

    items = data.get("items", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise RuntimeError("Konkurskupp feed must contain a list or an items list")

    needle = keyword.casefold().strip() if keyword and keyword.strip() else None
    documents: list[SourceDocument] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or "").strip()
        url = str(item.get("url") or item.get("source_url") or "").strip()
        if not title or not url.startswith("https://"):
            continue
        description = str(item.get("description") or "").strip()
        if needle and needle not in f"{title} {description}".casefold():
            continue
        raw_id = str(item.get("id") or "").strip()
        document_id = raw_id or hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        if document_id in seen:
            continue
        seen.add(document_id)
        price = _float_or_none(item.get("price_nok") or item.get("current_price_nok"))
        city = _text_or_none(item.get("city") or item.get("location"))
        ends_at = _datetime_or_none(item.get("ends_at"))
        documents.append(
            SourceDocument(
                document_id=f"konkurskupp-{document_id}",
                source_name="Konkurskupp",
                source_type="authorized_classified_ad",
                title=title,
                text=description or title,
                url=url,
                published_at=_datetime_or_none(item.get("published_at")),
                country="Norway",
                metadata={
                    "current_price_nok": price,
                    "city": city,
                    "ends_at": ends_at.isoformat() if ends_at else None,
                    "description": description or None,
                    "mva_status": str(item.get("mva_status") or "unknown"),
                    "access_mode": "authorized_feed",
                },
            )
        )
    return tuple(documents)


def _float_or_none(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _text_or_none(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _datetime_or_none(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
