"""Generic authorized JSON feed adapter for planned Norwegian sources.

The adapter never crawls public pages or bypasses access controls. It accepts only
an operator-supplied HTTPS feed and preserves channel separation through an
explicit source_type.
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

JsonTransport = Callable[[str, float, dict[str, str]], bytes]


def _default_transport(url: str, timeout: float, headers: dict[str, str]) -> bytes:
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - operator supplied HTTPS feed
            return response.read()
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise RuntimeError("authorized feed authentication failed") from exc
        raise RuntimeError(f"authorized feed returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"authorized feed request failed: {exc.reason}") from exc


@dataclass(frozen=True)
class GenericAuthorizedFeedClient:
    source_name: str
    source_type: str
    feed_url: str
    token: str | None = None
    timeout: float = 15.0
    transport: JsonTransport = _default_transport

    def __post_init__(self) -> None:
        if not self.source_name.strip():
            raise ValueError("source_name must not be empty")
        if not self.source_type.strip():
            raise ValueError("source_type must not be empty")
        if not self.feed_url.startswith("https://"):
            raise ValueError("feed_url must use HTTPS")
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
        return parse_authorized_feed(
            payload,
            source_name=self.source_name,
            source_type=self.source_type,
            keyword=keyword,
        )


def parse_authorized_feed(
    payload: bytes | str,
    *,
    source_name: str,
    source_type: str,
    keyword: str | None = None,
) -> tuple[SourceDocument, ...]:
    try:
        decoded = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        data = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise RuntimeError("authorized feed returned invalid JSON") from exc

    items = data.get("items", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise RuntimeError("authorized feed must contain a list or an items list")

    needle = keyword.casefold().strip() if keyword and keyword.strip() else None
    documents: list[SourceDocument] = []
    seen: set[str] = set()
    prefix = "".join(character for character in source_name.casefold() if character.isalnum()) or "source"

    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or "").strip()
        url = str(item.get("url") or item.get("source_url") or "").strip()
        if not title or not url.startswith("https://"):
            continue
        description = str(item.get("description") or item.get("summary") or "").strip()
        if needle and needle not in f"{title} {description}".casefold():
            continue
        raw_id = str(item.get("id") or item.get("event_id") or item.get("asset_id") or "").strip()
        document_id = raw_id or hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        if document_id in seen:
            continue
        seen.add(document_id)
        published_at = _datetime_or_none(item.get("published_at"))
        ends_at = _datetime_or_none(item.get("ends_at") or item.get("deadline"))
        documents.append(
            SourceDocument(
                document_id=f"{prefix}-{document_id}",
                source_name=source_name,
                source_type=source_type,
                title=title,
                text=description or title,
                url=url,
                published_at=published_at,
                country="Norway",
                metadata={
                    "description": description or None,
                    "city": _text_or_none(item.get("city") or item.get("location")),
                    "organization_number": _text_or_none(item.get("organization_number")),
                    "trustee": _text_or_none(item.get("trustee")),
                    "asset_type": _text_or_none(item.get("asset_type") or item.get("category")),
                    "ends_at": ends_at.isoformat() if ends_at else None,
                    "current_price_nok": _float_or_none(item.get("price_nok") or item.get("current_price_nok")),
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
