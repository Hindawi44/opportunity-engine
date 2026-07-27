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

AUKSJONEN_CATEGORY_URL = "https://www.auksjonen.no/auksjoner/vareparti_konkursbo"
_PRICE_RE = re.compile(
    r"(?<!\d)(\d{1,3}(?:[ \u00a0.]\d{3})+|\d+)\s*(?:(?:kr|nok)\b|,-)",
    re.IGNORECASE,
)
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
_EMPTY_STATE_TERMS = (
    "ingen auksjoner funnet",
    "ingen resultater funnet",
    "det finnes ingen auksjoner",
    "ingen objekter funnet",
)
_HYDRATION_MARKERS = (
    "__next_data__",
    "__nuxt__",
    "data-reactroot",
    "data-react-root",
    "ng-version",
)


@dataclass(frozen=True, slots=True)
class RawListing:
    listing_id: str
    title: str
    url: str
    asking_price_nok: float
    location: str | None = None
    listing_status: str = "ACTIVE"


@dataclass(frozen=True, slots=True)
class PublicPageResponse:
    html: str
    requested_url: str
    final_url: str
    http_status: int
    content_type: str
    response_byte_count: int


@dataclass(frozen=True, slots=True)
class PublicPageExtraction:
    listings: tuple[RawListing, ...]
    source_extraction_status: str
    diagnostics: dict[str, Any]


class _PublicPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.json_ld: list[str] = []
        self.application_json: list[str] = []
        self.anchor_count = 0
        self.html_title: str | None = None
        self.hydration_container_present = False
        self._href: str | None = None
        self._link_text: list[str] = []
        self._script_kind: str | None = None
        self._script_text: list[str] = []
        self._in_title = False
        self._title_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value for key, value in attrs}
        lowered_tag = tag.lower()
        if lowered_tag == "a" and values.get("href"):
            self.anchor_count += 1
            self._href = str(values["href"])
            self._link_text = []
        if lowered_tag == "script":
            script_type = str(values.get("type") or "").lower()
            if "ld+json" in script_type:
                self._script_kind = "ld+json"
                self._script_text = []
            elif "application/json" in script_type:
                self._script_kind = "application/json"
                self._script_text = []
        if lowered_tag == "title":
            self._in_title = True
            self._title_text = []

        marker_text = " ".join(
            str(value or "")
            for key, value in values.items()
            if key in {"id", "class", "data-reactroot"}
        ).casefold()
        if any(marker in marker_text for marker in _HYDRATION_MARKERS):
            self.hydration_container_present = True

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._link_text.append(data)
        if self._script_kind is not None:
            self._script_text.append(data)
        if self._in_title:
            self._title_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        lowered_tag = tag.lower()
        if lowered_tag == "a" and self._href is not None:
            text = " ".join(" ".join(self._link_text).split())
            self.links.append((self._href, text))
            self._href = None
            self._link_text = []
        if lowered_tag == "script" and self._script_kind is not None:
            payload = "".join(self._script_text)
            if self._script_kind == "ld+json":
                self.json_ld.append(payload)
            else:
                self.application_json.append(payload)
            self._script_kind = None
            self._script_text = []
        if lowered_tag == "title" and self._in_title:
            title = " ".join(" ".join(self._title_text).split())
            self.html_title = title or None
            self._in_title = False
            self._title_text = []


def fetch_public_page_response(
    url: str = AUKSJONEN_CATEGORY_URL,
    *,
    timeout: int = 30,
) -> PublicPageResponse:
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
        payload = response.read()
        return PublicPageResponse(
            html=payload.decode("utf-8", errors="replace"),
            requested_url=url,
            final_url=str(response.geturl()),
            http_status=int(response.status),
            content_type=content_type,
            response_byte_count=len(payload),
        )


def fetch_public_page(url: str = AUKSJONEN_CATEGORY_URL, *, timeout: int = 30) -> str:
    return fetch_public_page_response(url, timeout=timeout).html


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
    return "/auksjon/" in parsed.path.lower() or "/auksjoner/" in parsed.path.lower()


def _walk_json(value: object) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _from_json_payloads(payloads: Iterable[str], category_url: str) -> list[RawListing]:
    listings: list[RawListing] = []
    for raw in payloads:
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
            listings.append(RawListing(_listing_id(url), title, url, amount, location, status))
    return listings


def _title_from_link_text(text: str) -> str:
    cleaned = _PRICE_RE.sub("", text)
    marker_positions = [
        position
        for marker in (
            " Avsluttet",
            " Avsluttes",
            " Gjenstår",
            " Høyeste bud",
            " Fastpris",
            " Bud",
            " Sted",
        )
        if (position := cleaned.find(marker)) >= 0
    ]
    if marker_positions:
        cleaned = cleaned[: min(marker_positions)]
    return cleaned.strip(" -–|\n\t")


def _location_from_link_text(text: str) -> str | None:
    match = re.search(
        r"\bSted\s*\d{4}\s+([A-ZÆØÅ][A-ZÆØÅ\s-]*?)(?:\s+favorite_border|$)",
        text,
    )
    return " ".join(match.group(1).split()) if match else None


def _from_links(parser: _PublicPageParser, category_url: str) -> list[RawListing]:
    listings: list[RawListing] = []
    for href, text in parser.links:
        url = urljoin(category_url, href)
        amount = _price(text)
        title = _title_from_link_text(text)
        if amount is None or len(title) < 3 or not _valid_listing_url(url, category_url):
            continue
        listings.append(
            RawListing(
                _listing_id(url),
                title,
                url,
                amount,
                _location_from_link_text(text),
                _listing_status(text),
            )
        )
    return listings


def _parse(html: str, category_url: str) -> tuple[_PublicPageParser, list[RawListing]]:
    parser = _PublicPageParser()
    parser.feed(html)
    merged: dict[str, RawListing] = {}
    json_payloads = [*parser.json_ld, *parser.application_json]
    for item in [*_from_json_payloads(json_payloads, category_url), *_from_links(parser, category_url)]:
        merged.setdefault(item.listing_id, item)
    return parser, sorted(merged.values(), key=lambda item: item.listing_id)


def parse_public_listings(
    html: str,
    *,
    category_url: str = AUKSJONEN_CATEGORY_URL,
) -> list[RawListing]:
    _, listings = _parse(html, category_url)
    return listings


def inspect_public_page(
    html: str,
    *,
    category_url: str = AUKSJONEN_CATEGORY_URL,
    requested_url: str | None = None,
    final_url: str | None = None,
    http_status: int | None = None,
    content_type: str | None = None,
    response_byte_count: int | None = None,
) -> PublicPageExtraction:
    parser, listings = _parse(html, category_url)
    normalized = " ".join(html.casefold().split())
    explicit_empty = any(term in normalized for term in _EMPTY_STATE_TERMS)
    if listings:
        status = "VERIFIED_LISTINGS"
    elif explicit_empty:
        status = "VERIFIED_EMPTY"
    else:
        status = "UNVERIFIED_ZERO"

    diagnostics = {
        "requested_url": requested_url or category_url,
        "final_url": final_url or category_url,
        "http_status": http_status,
        "content_type": content_type,
        "response_byte_count": (
            response_byte_count
            if response_byte_count is not None
            else len(html.encode("utf-8"))
        ),
        "html_title": parser.html_title,
        "anchor_count": parser.anchor_count,
        "application_ld_json_count": len(parser.json_ld),
        "application_json_count": len(parser.application_json),
        "hydration_container_present": parser.hydration_container_present,
        "explicit_empty_state_present": explicit_empty,
    }
    return PublicPageExtraction(tuple(listings), status, diagnostics)


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
