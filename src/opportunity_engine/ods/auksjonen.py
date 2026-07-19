"""Public Auksjonen.no listing connector.

Auksjonen.no does not expose a documented public API for this use case. This
connector therefore reads public listing pages only. It does not log in,
bypass access controls, or submit bids. Network access is isolated behind an
injectable transport so parsing can be tested without live requests.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
import hashlib
import json
import re
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urljoin
from urllib.request import Request, urlopen

from .live_data import SourceDocument
from .models import ODSRequest

AUKSJONEN_BASE_URL = "https://www.auksjonen.no"
AUKSJONEN_LISTINGS_URL = f"{AUKSJONEN_BASE_URL}/auksjoner/"
HtmlTransport = Callable[[str, float, dict[str, str]], str]


def _default_html_transport(url: str, timeout: float, headers: dict[str, str]) -> str:
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS host
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except HTTPError as exc:
        raise RuntimeError(f"Auksjonen returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Auksjonen request failed: {exc.reason}") from exc


@dataclass(frozen=True)
class AuksjonenClient:
    """Small client for public Auksjonen listing pages."""

    timeout: float = 15.0
    base_url: str = AUKSJONEN_BASE_URL
    transport: HtmlTransport = _default_html_transport

    def __post_init__(self) -> None:
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        if not self.base_url.startswith("https://"):
            raise ValueError("Auksjonen base_url must use HTTPS")

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "Opportunity-Engine/1.0 (+public-listing-research)",
        }

    def search(self, *, keyword: str | None = None) -> tuple[SourceDocument, ...]:
        url = f"{self.base_url}/auksjoner/"
        if keyword and keyword.strip():
            url = f"{url}?q={quote_plus(keyword.strip())}"
        html = self.transport(url, self.timeout, self.headers)
        return parse_auksjonen_listing_page(html, base_url=self.base_url)


@dataclass(frozen=True)
class AuksjonenConnector:
    """Normalize public Auksjonen listings into ODS source documents."""

    client: AuksjonenClient
    name: str = "auksjonen_public_listings"

    def fetch(self, request: ODSRequest) -> tuple[SourceDocument, ...]:
        return self.client.search(keyword=request.subject)


def parse_auksjonen_listing_page(
    html: str,
    *,
    base_url: str = AUKSJONEN_BASE_URL,
) -> tuple[SourceDocument, ...]:
    """Parse public auction listings using structured data and safe fallbacks."""
    if not html.strip():
        return ()

    records = _parse_json_ld(html)
    if not records:
        parser = _ListingAnchorParser(base_url)
        parser.feed(html)
        records = parser.records

    documents: list[SourceDocument] = []
    seen: set[str] = set()
    for record in records:
        url = record.get("url")
        title = _clean_text(record.get("title"))
        if not title or not url:
            continue
        absolute_url = urljoin(base_url, url)
        auction_id = _auction_id(absolute_url, title)
        if auction_id in seen:
            continue
        seen.add(auction_id)

        price = _parse_price(record.get("price") or record.get("text"))
        city = _clean_text(record.get("city")) or _extract_city(record.get("text", ""))
        ends_at = _parse_datetime(record.get("ends_at"))
        text_parts = [title]
        if price is not None:
            text_parts.append(f"Current price: {price:.0f} NOK")
        if city:
            text_parts.append(f"Location: {city}")
        if ends_at:
            text_parts.append(f"Ends at: {ends_at.isoformat()}")

        documents.append(
            SourceDocument(
                document_id=f"auksjonen-{auction_id}",
                source_name="Auksjonen.no",
                source_type="public_auction_listing",
                title=title,
                text=" | ".join(text_parts),
                url=absolute_url,
                published_at=None,
                country="Norway",
                metadata={
                    "auction_id": auction_id,
                    "current_price_nok": price,
                    "city": city,
                    "ends_at": ends_at.isoformat() if ends_at else None,
                    "access_mode": "public_listing_page",
                },
            )
        )
    return tuple(documents)


def _parse_json_ld(html: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    pattern = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(html):
        try:
            payload = json.loads(match.group(1).strip())
        except (json.JSONDecodeError, TypeError):
            continue
        for item in _walk_json(payload):
            item_type = str(item.get("@type", "")).casefold()
            if item_type not in {"product", "offer", "listitem"}:
                continue
            nested = item.get("item") if isinstance(item.get("item"), dict) else {}
            offers = item.get("offers") if isinstance(item.get("offers"), dict) else {}
            address = item.get("address") if isinstance(item.get("address"), dict) else {}
            records.append(
                {
                    "title": str(item.get("name") or nested.get("name") or ""),
                    "url": str(item.get("url") or nested.get("url") or ""),
                    "price": str(item.get("price") or offers.get("price") or ""),
                    "city": str(address.get("addressLocality") or ""),
                    "ends_at": str(item.get("validThrough") or offers.get("validThrough") or ""),
                    "text": str(item.get("description") or nested.get("description") or ""),
                }
            )
    return records


def _walk_json(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


class _ListingAnchorParser(HTMLParser):
    """Fallback parser for listing links when JSON-LD is unavailable."""

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.records: list[dict[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        values = dict(attrs)
        href = values.get("href")
        if href and _looks_like_auction_url(href):
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._href:
            return
        text = _clean_text(" ".join(self._text))
        if text:
            self.records.append(
                {
                    "title": _title_from_anchor_text(text),
                    "url": self._href,
                    "text": text,
                    "price": text,
                    "city": "",
                    "ends_at": "",
                }
            )
        self._href = None
        self._text = []


def _looks_like_auction_url(href: str) -> bool:
    normalized = href.casefold()
    return "/auksjon" in normalized and not normalized.rstrip("/").endswith("/auksjoner")


def _title_from_anchor_text(text: str) -> str:
    for marker in ("Avsluttes", "Gjenstår", "Høyeste bud", "Kjøp nå", "Bud"):
        if marker.casefold() in text.casefold():
            index = text.casefold().find(marker.casefold())
            return text[:index].strip(" -|") or text
    return text


def _parse_price(value: str | None) -> float | None:
    if not value:
        return None
    matches = re.findall(r"(?:NOK|kr)?\s*([0-9][0-9 .\u00a0]*)\s*(?:,-|kr|NOK)?", value, re.IGNORECASE)
    if not matches:
        return None
    cleaned = re.sub(r"[^0-9]", "", matches[-1])
    return float(cleaned) if cleaned else None


def _extract_city(text: str) -> str | None:
    match = re.search(r"(?:Sted|Lokasjon|Location)\s*[:|-]\s*([A-Za-zÆØÅæøå .-]{2,50})", text)
    return _clean_text(match.group(1)) if match else None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _auction_id(url: str, title: str) -> str:
    match = re.search(r"(?:auksjon|auction)[^0-9]*(\d{4,})", url, re.IGNORECASE)
    if match:
        return match.group(1)
    digest = hashlib.sha256(f"{url}|{title}".encode("utf-8")).hexdigest()
    return digest[:16]


def _clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()
