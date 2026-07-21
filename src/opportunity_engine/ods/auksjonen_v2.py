"""Connector for the current public Auksjonen.no listings page.

The current site redirects the legacy listings URL to ``ny.auksjonen.no``.
This connector parses public auction anchors directly and does not require
login, private APIs, or browser automation.
"""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import hashlib
import re
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urljoin
from urllib.request import Request, urlopen

from .live_data import SourceDocument

AUKSJONEN_BASE_URL = "https://ny.auksjonen.no"
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
    timeout: float = 20.0
    base_url: str = AUKSJONEN_BASE_URL
    transport: HtmlTransport = _default_html_transport

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "nb-NO,nb;q=0.9,en;q=0.7",
            "User-Agent": "Mozilla/5.0 (compatible; Opportunity-Engine/1.0)",
        }

    def search(self, *, keyword: str | None = None) -> tuple[SourceDocument, ...]:
        url = f"{self.base_url}/auksjoner/alle"
        if keyword and keyword.strip():
            url = f"{url}?q={quote_plus(keyword.strip())}"
        html = self.transport(url, self.timeout, self.headers)
        documents = parse_auksjonen_listing_page(html, base_url=self.base_url)
        if keyword and keyword.strip():
            needle = keyword.strip().casefold()
            documents = tuple(x for x in documents if needle in x.title.casefold() or needle in x.text.casefold())
        return documents


class _AuctionAnchorParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.records: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a" or self._href is not None:
            return
        href = dict(attrs).get("href")
        if href and "/auksjon/" in href.casefold():
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self._href is None:
            return
        text = _clean_text(" ".join(self._text))
        if text:
            self.records.append((urljoin(self.base_url, self._href), text))
        self._href = None
        self._text = []


def parse_auksjonen_listing_page(html: str, *, base_url: str = AUKSJONEN_BASE_URL) -> tuple[SourceDocument, ...]:
    parser = _AuctionAnchorParser(base_url)
    parser.feed(html)
    documents: list[SourceDocument] = []
    seen: set[str] = set()
    for url, text in parser.records:
        auction_id = _auction_id(url)
        if auction_id in seen:
            continue
        seen.add(auction_id)
        title = _extract_title(text)
        if not title:
            continue
        price = _parse_price(text)
        documents.append(SourceDocument(
            document_id=f"auksjonen-{auction_id}",
            source_name="Auksjonen.no",
            source_type="public_auction_listing",
            title=title,
            text=text,
            url=url,
            published_at=None,
            country="Norway",
            metadata={"auction_id": auction_id, "current_price_nok": price, "city": None, "ends_at": None, "parser_version": 2},
        ))
    return tuple(documents)


def _auction_id(url: str) -> str:
    match = re.search(r"/(\d{4,})(?:[/?#]|$)", url)
    return match.group(1) if match else hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _extract_title(text: str) -> str:
    value = re.sub(r"^(?:Video\s+)?(?:Uten minstepris\s+|Minstepris oppnådd\s+)?", "", text, flags=re.IGNORECASE)
    for marker in (" Høyeste bud ", " Fastpris ", " Kjøp nå ", " Avsluttes "):
        index = value.casefold().find(marker.casefold())
        if index > 8:
            value = value[:index]
            break
    return _clean_text(value)


def _parse_price(text: str) -> float | None:
    for pattern in (r"Høyeste bud\s+([0-9][0-9 .\u00a0]*)\s*,-", r"Fastpris\s+([0-9][0-9 .\u00a0]*)\s*,-"):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            cleaned = re.sub(r"[^0-9]", "", match.group(1))
            return float(cleaned) if cleaned else None
    return None


def _clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()
