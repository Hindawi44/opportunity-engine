"""Authorized Konkurs.app feed connector.

This connector accepts only an explicitly authorized JSON feed or operator export.
It does not crawl public pages, authenticate through a browser, or bypass access
controls.
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
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - authorized HTTPS feed
            return response.read()
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise RuntimeError("Konkurs.app feed authorization failed") from exc
        raise RuntimeError(f"Konkurs.app feed returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Konkurs.app feed request failed: {exc.reason}") from exc


@dataclass(frozen=True)
class KonkursAppFeedClient:
    feed_url: str
    token: str | None = None
    timeout: float = 15.0
    transport: JsonTransport = _default_json_transport

    def __post_init__(self) -> None:
        if not self.feed_url.startswith("https://"):
            raise ValueError("Konkurs.app feed_url must use HTTPS")
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
        return parse_konkurs_app_feed(payload, keyword=keyword)


@dataclass(frozen=True)
class KonkursAppConnector:
    client: KonkursAppFeedClient
    name: str = "konkurs_app_authorized_feed"

    def fetch(self, request: ODSRequest) -> tuple[SourceDocument, ...]:
        return self.client.fetch(keyword=request.subject)


def parse_konkurs_app_feed(
    payload: bytes | str,
    *,
    keyword: str | None = None,
) -> tuple[SourceDocument, ...]:
    try:
        decoded = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        data = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise RuntimeError("Konkurs.app feed returned invalid JSON") from exc

    items = data.get("items", data.get("results", data)) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise RuntimeError("Konkurs.app feed must contain a list, items list, or results list")

    needle = keyword.casefold().strip() if keyword and keyword.strip() else None
    documents: list[SourceDocument] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("company_name") or item.get("name") or "").strip()
        url = str(item.get("url") or item.get("source_url") or "").strip()
        if not title or not url.startswith("https://"):
            continue
        description = str(item.get("description") or item.get("summary") or "").strip()
        organization_number = _text_or_none(item.get("organization_number") or item.get("orgnr"))
        searchable = f"{title} {description} {organization_number or ''}".casefold()
        if needle and needle not in searchable:
            continue

        raw_id = str(item.get("id") or item.get("case_id") or organization_number or "").strip()
        document_id = raw_id or hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        if document_id in seen:
            continue
        seen.add(document_id)

        city = _text_or_none(item.get("city") or item.get("location") or item.get("municipality"))
        deadline = _datetime_or_none(item.get("ends_at") or item.get("deadline"))
        bankruptcy_date = _datetime_or_none(item.get("bankruptcy_date") or item.get("opened_at"))
        price = _float_or_none(item.get("price_nok") or item.get("current_price_nok"))
        documents.append(
            SourceDocument(
                document_id=f"konkurs-app-{document_id}",
                source_name="Konkurs.app",
                source_type="authorized_liquidation_asset",
                title=title,
                text=description or title,
                url=url,
                published_at=bankruptcy_date or _datetime_or_none(item.get("published_at")),
                country="Norway",
                metadata={
                    "current_price_nok": price,
                    "city": city,
                    "ends_at": deadline.isoformat() if deadline else None,
                    "description": description or None,
                    "organization_number": organization_number,
                    "bankruptcy_date": bankruptcy_date.isoformat() if bankruptcy_date else None,
                    "asset_type": _text_or_none(item.get("asset_type") or item.get("category")),
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
