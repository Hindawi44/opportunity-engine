"""FINN Torget public-page ingestion for V3.6.

Extracts raw public listings only. No authentication bypass, private API use,
or inference of missing evidence is performed.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Iterable
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen

FINN_TORGET_URL = "https://www.finn.no/bap/forsale/search.html"
_PRICE_RE = re.compile(r"(?<!\d)(\d[\d\s\u00a0.]*)\s*(?:kr|nok)\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class FinnRawListing:
    listing_id: str
    title: str
    url: str
    asking_price_nok: float
    location: str | None = None


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.json_ld: list[str] = []
        self._href: str | None = None
        self._text: list[str] = []
        self._in_json = False
        self._script: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {k.lower(): v for k, v in attrs}
        if tag.lower() == "a" and values.get("href"):
            self._href = str(values["href"])
            self._text = []
        if tag.lower() == "script" and "ld+json" in str(values.get("type") or "").lower():
            self._in_json = True
            self._script = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)
        if self._in_json:
            self._script.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(" ".join(self._text).split())))
            self._href = None
        if tag.lower() == "script" and self._in_json:
            self.json_ld.append("".join(self._script))
            self._in_json = False


def fetch_public_page(url: str = FINN_TORGET_URL, *, timeout: int = 30) -> str:
    request = Request(url, headers={
        "User-Agent": "OpportunityEngine/3.6 (+public-source-ingestion)",
        "Accept": "text/html,application/xhtml+xml",
    })
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - explicit public HTTPS source
        content_type = str(response.headers.get("Content-Type") or "")
        if response.status != 200:
            raise RuntimeError(f"FINN returned HTTP {response.status}")
        if "html" not in content_type.lower():
            raise RuntimeError(f"FINN returned unsupported content type: {content_type}")
        return response.read().decode("utf-8", errors="replace")


def _price(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return float(value)
    if isinstance(value, str):
        match = _PRICE_RE.search(value)
        if match:
            normalized = match.group(1).replace("\u00a0", "").replace(" ", "").replace(".", "")
            try:
                amount = float(normalized)
            except ValueError:
                return None
            return amount if amount > 0 else None
    return None


def _valid_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() not in {"www.finn.no", "finn.no"}:
        return False
    return "/bap/forsale/ad.html" in parsed.path.lower() and bool(parse_qs(parsed.query).get("finnkode"))


def _listing_id(url: str) -> str:
    values = parse_qs(urlparse(url).query).get("finnkode") or []
    if values and values[0].isdigit():
        return values[0]
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]


def _walk(value: object) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def parse_public_listings(html: str, *, search_url: str = FINN_TORGET_URL) -> list[FinnRawListing]:
    parser = _Parser()
    parser.feed(html)
    merged: dict[str, FinnRawListing] = {}
    for raw in parser.json_ld:
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        for item in _walk(payload):
            title = str(item.get("name") or item.get("title") or "").strip()
            url = urljoin(search_url, str(item.get("url") or "").strip())
            offers = item.get("offers") if isinstance(item.get("offers"), dict) else {}
            amount = _price(offers.get("price")) or _price(item.get("price"))
            location = None
            address = item.get("address") or item.get("location")
            if isinstance(address, dict):
                location = str(address.get("addressLocality") or address.get("name") or "").strip() or None
            if title and amount is not None and _valid_url(url):
                listing = FinnRawListing(_listing_id(url), title, url, amount, location)
                merged[listing.listing_id] = listing
    for href, text in parser.links:
        url = urljoin(search_url, href)
        amount = _price(text)
        title = _PRICE_RE.sub("", text).strip(" -–|\n\t")
        if amount is not None and len(title) >= 3 and _valid_url(url):
            listing = FinnRawListing(_listing_id(url), title, url, amount)
            merged.setdefault(listing.listing_id, listing)
    return sorted(merged.values(), key=lambda item: item.listing_id)


def build_snapshot(
    listings: Iterable[FinnRawListing], *, search_url: str = FINN_TORGET_URL,
    captured_at: str | None = None,
) -> dict[str, Any]:
    timestamp = captured_at or datetime.now(timezone.utc).isoformat()
    opportunities = []
    for listing in listings:
        opportunities.append({
            "schema_version": "3.6",
            "opportunity_id": f"finn-{listing.listing_id}",
            "captured_at": timestamp,
            "source": {
                "name": "FINN.no",
                "listing_id": listing.listing_id,
                "url": listing.url,
                "title": listing.title,
                "location": listing.location,
                "listing_status": "ACTIVE",
                "asking_price_nok": listing.asking_price_nok,
            },
            "market_price_sources": [],
            "verified_cost_evidence": {
                "auction_price_nok": listing.asking_price_nok,
                "auction_fee_nok": None,
                "vat_nok": None,
                "transport_cost_nok": None,
                "dismantling_cost_nok": None,
                "storage_cost_nok": None,
            },
            "blocking_missing_evidence": [
                "three_verified_market_comparables", "auction_fee_nok", "vat_nok",
                "transport_cost_nok", "dismantling_cost_nok", "storage_cost_nok",
            ],
        })
    return {
        "schema_version": "3.6", "captured_at": timestamp,
        "source_page": search_url, "source": "FINN.no", "opportunities": opportunities,
    }
