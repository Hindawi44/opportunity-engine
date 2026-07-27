"""Auksjonen.no public-page ingestion for V3.3.

This adapter extracts raw listing snapshots only. It does not infer missing prices,
market comparables, logistics costs, or financial decisions.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

AUKSJONEN_CATEGORY_URL = (
    "https://www.auksjonen.no/auksjoner/overskuddsvarer/"
    "vareparti-og-konkursbo"
)
_PRICE_RE = re.compile(r"(?<!\d)(\d[\d\s\u00a0.]*)\s*(?:kr|nok)\b", re.IGNORECASE)
_ID_RE = re.compile(r"(?:^|[-_/])(\d{4,})(?:$|[/?#])")
_ENDED_TERMS = (
    "avsluttet",
    "utløpt",
    "utlopt",
    "soldout",
    "outofstock",
    "discontinued",
)
_ACTIVE_TERMS = (
    "avsluttes",
    "gjenstår",
    "gjenstar",
    "gi bud",
    "instock",
    "preorder",
    "limitedavailability",
)


@dataclass(frozen=True, slots=True)
class RawListing:
    listing_id: str
    title: str
    url: str
    asking_price_nok: float
    location: str | None = None
    listing_status: str = "ACTIVE"


class _PublicPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.json_ld: list[str] = []
        self._href: str | None = None
        self._link_text: list[str] = []
        self._in_json_ld = False
        self._script_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value for key, value in attrs}
        if tag.lower() == "a" and values.get("href"):
            self._href = str(values["href"])
            self._link_text = []
        if tag.lower() == "script" and "ld+json" in str(values.get("type") or "").lower():
            self._in_json_ld = True
            self._script_text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._link_text.append(data)
        if self._in_json_ld:
            self._script_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            text = " ".join(" ".join(self._link_text).split())
            self.links.append((self._href, text))
            self._href = None
            self._link_text = []
        if tag.lower() == "script" and self._in_json_ld:
            self.json_ld.append("".join(self._script_text))
            self._in_json_ld = False
            self._script_text = []


def fetch_public_page(url: str = AUKSJONEN_CATEGORY_URL, *, timeout: int = 30) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "OpportunityEngine/3.3 (+public-source-ingestion)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed public HTTPS source
        content_type = str(response.headers.get("Content-Type") or "")
        if response.status != 200:
            raise RuntimeError(f"Auksjonen returned HTTP {response.status}")
        if "html" not in content_type.lower():
            raise RuntimeError(f"Auksjonen returned unsupported content type: {content_type}")
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


def _listing_status(*values: object) -> str:
    """Preserve explicit public active/ended markers without inferring dates."""
    normalized = " ".join(str(value) for value in values if value is not None).casefold()
    if any(term in normalized for term in _ENDED_TERMS):
        return "ENDED"
    if any(term in normalized for term in _ACTIVE_TERMS):
        return "ACTIVE"
    return "ACTIVE"


def _listing_id(url: str) -> str:
    match = _ID_RE.search(urlparse(url).path)
    if match:
        return match.group(1)
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]


def _valid_listing_url(url: str, category_url: str) -> bool:
    parsed = urlparse(url)
    category = urlparse(category_url)
    if parsed.scheme != "https" or parsed.netloc.lower() != category.netloc.lower():
        return False
    if url.rstrip("/") == category_url.rstrip("/"):
        return False
    return "/auksjon" in parsed.path.lower()


def _walk_json(value: object) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _from_json_ld(parser: _PublicPageParser, category_url: str) -> list[RawListing]:
    listings: list[RawListing] = []
    for raw in parser.json_ld:
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        for item in _walk_json(payload):
            title = str(item.get("name") or item.get("title") or "").strip()
            url = urljoin(category_url, str(item.get("url") or "").strip())
            offers = item.get("offers") if isinstance(item.get("offers"), dict) else {}
            amount = _price(offers.get("price")) or _price(item.get("price"))
            if not title or amount is None or not _valid_listing_url(url, category_url):
                continue
            location_data = item.get("location")
            location = None
            if isinstance(location_data, dict):
                location = str(location_data.get("name") or "").strip() or None
            status = _listing_status(
                offers.get("availability"),
                item.get("availability"),
                item.get("status"),
            )
            listings.append(
                RawListing(_listing_id(url), title, url, amount, location, status)
            )
    return listings


def _from_links(parser: _PublicPageParser, category_url: str) -> list[RawListing]:
    listings: list[RawListing] = []
    for href, text in parser.links:
        url = urljoin(category_url, href)
        amount = _price(text)
        title = _PRICE_RE.sub("", text).strip(" -–|\n\t")
        if amount is None or len(title) < 3 or not _valid_listing_url(url, category_url):
            continue
        listings.append(
            RawListing(
                _listing_id(url),
                title,
                url,
                amount,
                listing_status=_listing_status(text),
            )
        )
    return listings


def parse_public_listings(html: str, *, category_url: str = AUKSJONEN_CATEGORY_URL) -> list[RawListing]:
    parser = _PublicPageParser()
    parser.feed(html)
    merged: dict[str, RawListing] = {}
    for item in [*_from_json_ld(parser, category_url), *_from_links(parser, category_url)]:
        merged[item.listing_id] = item
    return sorted(merged.values(), key=lambda item: item.listing_id)


def build_snapshot(
    listings: Iterable[RawListing],
    *,
    category_url: str = AUKSJONEN_CATEGORY_URL,
    captured_at: str | None = None,
) -> dict[str, Any]:
    timestamp = captured_at or datetime.now(timezone.utc).isoformat()
    opportunities: list[dict[str, Any]] = []
    for listing in listings:
        opportunities.append({
            "schema_version": "3.3",
            "opportunity_id": f"auksjonen-{listing.listing_id}",
            "captured_at": timestamp,
            "source": {
                "name": "Auksjonen.no",
                "listing_id": listing.listing_id,
                "url": listing.url,
                "title": listing.title,
                "location": listing.location,
                "listing_status": listing.listing_status,
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
                "three_verified_market_comparables",
                "auction_fee_nok",
                "vat_nok",
                "transport_cost_nok",
                "dismantling_cost_nok",
                "storage_cost_nok",
            ],
        })
    return {
        "schema_version": "3.3",
        "captured_at": timestamp,
        "source_page": category_url,
        "source": "Auksjonen.no",
        "opportunities": opportunities,
    }
