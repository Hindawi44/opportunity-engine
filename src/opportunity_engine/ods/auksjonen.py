"""Public connector for Auksjonen.no listing pages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
import hashlib
import json
import re
from typing import Callable, Iterable
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
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
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

    def __post_init__(self) -> None:
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        if not self.base_url.startswith("https://"):
            raise ValueError("Auksjonen base_url must use HTTPS")

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "nb-NO,nb;q=0.9,en;q=0.7",
            "User-Agent": "Mozilla/5.0 (compatible; Opportunity-Engine/1.0)",
        }

    def search(self, *, keyword: str | None = None) -> tuple[SourceDocument, ...]:
        url = f"{self.base_url}/auksjoner/"
        if keyword and keyword.strip():
            url = f"{url}?q={quote_plus(keyword.strip())}"
        html = self.transport(url, self.timeout, self.headers)
        return parse_auksjonen_listing_page(html, base_url=self.base_url)


@dataclass(frozen=True)
class AuksjonenConnector:
    client: AuksjonenClient
    name: str = "auksjonen_public_listings"

    def fetch(self, request: ODSRequest) -> tuple[SourceDocument, ...]:
        return self.client.search(keyword=request.subject)


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
    if not html.strip():
        return ()

    documents: list[SourceDocument] = []
    seen: set[str] = set()

    for item in _iter_json_ld_products(html):
        document = _document_from_json_ld(item, base_url=base_url)
        if document is None or document.document_id in seen:
            continue
        seen.add(document.document_id)
        documents.append(document)

    parser = _AuctionAnchorParser(base_url)
    parser.feed(html)
    for url, text in parser.records:
        auction_id = _auction_id(url)
        document_id = f"auksjonen-{auction_id}"
        if document_id in seen:
            continue
        title = _extract_title(text)
        if not title:
            continue
        price, price_type = _extract_price(text)
        seen.add(document_id)
        documents.append(
            SourceDocument(
                document_id=document_id,
                source_name="Auksjonen.no",
                source_type="public_auction_listing",
                title=title,
                text=text,
                url=url,
                published_at=None,
                country="Norway",
                metadata={
                    "auction_id": auction_id,
                    "current_price_nok": price,
                    "price_type": price_type,
                    "price_status": "verified_from_listing_text" if price is not None else "missing_from_listing_text",
                    "city": _extract_city(text, title),
                    "ends_at": None,
                    "access_mode": "public_listing_page",
                    "parser_version": 4,
                },
            )
        )
    return tuple(documents)


def _iter_json_ld_products(html: str) -> Iterable[dict[str, object]]:
    pattern = re.compile(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL)
    for match in pattern.finditer(html):
        try:
            payload = json.loads(match.group(1).strip())
        except (json.JSONDecodeError, TypeError):
            continue
        yield from _walk_json_ld(payload)


def _walk_json_ld(value: object) -> Iterable[dict[str, object]]:
    if isinstance(value, list):
        for item in value:
            yield from _walk_json_ld(item)
        return
    if not isinstance(value, dict):
        return
    item_type = str(value.get("@type") or "").casefold()
    if item_type in {"product", "offer"} and value.get("url"):
        yield value
    for key in ("@graph", "itemListElement", "item", "mainEntity"):
        child = value.get(key)
        if child is not None:
            yield from _walk_json_ld(child)


def _document_from_json_ld(item: dict[str, object], *, base_url: str) -> SourceDocument | None:
    raw_url = item.get("url")
    title = _clean_text(item.get("name"))
    if not raw_url or not title:
        return None
    url = urljoin(base_url, str(raw_url))
    auction_id = _auction_id(url)
    offers = _normalise_offer(item.get("offers"))
    address = item.get("address") if isinstance(item.get("address"), dict) else {}
    description = _clean_text(item.get("description"))
    price, price_type = _price_from_offer(offers)
    return SourceDocument(
        document_id=f"auksjonen-{auction_id}",
        source_name="Auksjonen.no",
        source_type="public_auction_listing",
        title=title,
        text=_clean_text(" ".join(part for part in (title, description) if part)),
        url=url,
        published_at=None,
        country="Norway",
        metadata={
            "auction_id": auction_id,
            "current_price_nok": price,
            "price_type": price_type,
            "price_status": "verified_from_json_ld" if price is not None else "missing_from_json_ld",
            "city": _clean_text(address.get("addressLocality")) or None,
            "ends_at": _valid_iso_datetime(offers.get("validThrough")),
            "access_mode": "public_listing_page",
            "parser_version": 4,
        },
    )


def _normalise_offer(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
    return {}


def _price_from_offer(offer: dict[str, object]) -> tuple[float | None, str | None]:
    for key, price_type in (
        ("price", "offer_price"),
        ("lowPrice", "low_price"),
        ("highPrice", "high_price"),
    ):
        price = _coerce_price(offer.get(key))
        if price is not None:
            return price, price_type
    return None, None


def _auction_id(url: str) -> str:
    match = re.search(r"/(\d{4,})(?:[/?#]|$)", url)
    if match:
        return match.group(1)
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _extract_title(text: str) -> str:
    value = re.sub(r"^(?:Video\s+)?(?:Uten minstepris\s+|Minstepris oppnådd\s+)?", "", text, flags=re.IGNORECASE)
    markers = (
        " Høyeste bud ",
        " Nåværende bud ",
        " Gjeldende bud ",
        " Startpris ",
        " Fastpris ",
        " Kjøp nå ",
        " Pris ",
        " Avsluttes snart ",
        " Avsluttes ",
        " Gjenstår ",
    )
    positions = [
        index
        for marker in markers
        if (index := value.casefold().find(marker.casefold())) > 0
    ]
    if positions:
        value = value[: min(positions)]
    return _clean_text(value)


def _extract_price(text: str) -> tuple[float | None, str | None]:
    patterns = (
        (r"Høyeste\s+bud\s*(?:er|:)??\s*(?:NOK|kr)?\s*([0-9][0-9 .\u00a0]*)\s*(?:NOK|kr|,-)?", "highest_bid"),
        (r"Nåværende\s+bud\s*(?:er|:)??\s*(?:NOK|kr)?\s*([0-9][0-9 .\u00a0]*)\s*(?:NOK|kr|,-)?", "current_bid"),
        (r"Gjeldende\s+bud\s*(?:er|:)??\s*(?:NOK|kr)?\s*([0-9][0-9 .\u00a0]*)\s*(?:NOK|kr|,-)?", "current_bid"),
        (r"Fastpris\s*(?:er|:)??\s*(?:NOK|kr)?\s*([0-9][0-9 .\u00a0]*)\s*(?:NOK|kr|,-)?", "fixed_price"),
        (r"Kjøp\s+nå\s*(?:for|:)??\s*(?:NOK|kr)?\s*([0-9][0-9 .\u00a0]*)\s*(?:NOK|kr|,-)?", "buy_now"),
        (r"Startpris\s*(?:er|:)??\s*(?:NOK|kr)?\s*([0-9][0-9 .\u00a0]*)\s*(?:NOK|kr|,-)?", "starting_price"),
    )
    for pattern, price_type in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            price = _coerce_price(match.group(1))
            if price is not None:
                return price, price_type
    return None, None


def _parse_price(text: str) -> float | None:
    """Backward-compatible wrapper used by older callers and tests."""
    return _extract_price(text)[0]


def _coerce_price(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value or "").strip()
    if not raw:
        return None
    digits = re.sub(r"[^0-9]", "", raw)
    if not digits:
        return None
    try:
        return float(digits)
    except ValueError:
        return None


def _valid_iso_datetime(value: object) -> str | None:
    candidate = _clean_text(value)
    if not candidate:
        return None
    try:
        datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        return None
    return candidate


def _extract_city(text: str, title: str) -> str | None:
    remainder = text[len(title):].strip()
    match = re.match(r"([A-Za-zÆØÅæøå][A-Za-zÆØÅæøå .-]{1,45}?)(?:\s+\d+\s+bud|\s+\d{2}\.\d{2}\.\d{4}|\s+Fastpris)", remainder)
    return _clean_text(match.group(1)) if match else None


def _clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()
