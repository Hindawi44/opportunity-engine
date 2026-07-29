"""Direct bounded adapter for Auksjonen's public live category API.

The endpoint and schema were observed from the public ny.auksjonen.no application.
This adapter scans every available page in the approved clothing category within
strict request and item limits, keeps active clothing-like items for source
visibility, and promotes only verified inventory-lot signals to opportunity
outputs. It uses no paid search or AI API and never logs in, contacts a seller,
bids, buys, reserves, or pays.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

DEFAULT_CATEGORY_ID = "10110508"
DEFAULT_PAGE_SIZE = 30
MAX_PAGE_SIZE = 30
MAX_PAGES = 10
MAX_LISTINGS = 300
DEFAULT_PUBLIC_API_ENDPOINT = (
    "https://ny.auksjonen.no/api/category-search/search"
    "?category2=10110508&from=1&to=30&asc=true&orderBy=endTime"
)
ACTIVE_STATUSES = frozenset({"ACTIVE", "INPROGRESS", "OPEN"})
_CLOTHING_PATTERN = re.compile(
    r"\b(klær|jakke|jakker|bukse|bukser|sko|kjole|kjoler|skjorte|skjorter|"
    r"genser|gensere|frakk|frakker|dress|dresser|vest|vester|tøy|arbeidsklær|"
    r"arbeidstøy|mc-klær|mote|tekstil|veske|vesker|overall|kjeledress|uniform)\b",
    re.I,
)
_LOT_PATTERN = re.compile(
    r"\b(?:vareparti|restlager|konkursbo|lagerbeholdning|varelager|parti|bulk|"
    r"samlet|pall(?:er)?|pakke\s+med|eske\s+med|flere\s+(?:stk|plagg|varer)|"
    r"\d+\s*(?:stk|plagg|jakker|bukser|kjoler|skjorter|gensere|sko|varer))\b",
    re.I,
)


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def _positive_int(value: object) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def is_approved_public_api_endpoint(url: str) -> bool:
    """Allow only bounded reads from the observed public clothing endpoint."""
    parsed = urlparse(str(url or "").strip())
    query = parse_qs(parsed.query)
    category = query.get("category2", [])
    start = _positive_int(query.get("from", [None])[0])
    end = _positive_int(query.get("to", [None])[0])
    return (
        parsed.scheme == "https"
        and parsed.hostname == "ny.auksjonen.no"
        and parsed.path == "/api/category-search/search"
        and category == [DEFAULT_CATEGORY_ID]
        and start is not None
        and end is not None
        and start <= end
        and end - start + 1 <= MAX_PAGE_SIZE
        and end <= MAX_PAGE_SIZE * MAX_PAGES
    )


def build_page_endpoint(endpoint: str, start: int, end: int) -> str:
    """Move the approved endpoint to one bounded inclusive result window."""
    if not is_approved_public_api_endpoint(endpoint):
        raise ValueError("endpoint is outside the approved Auksjonen clothing API")
    if start < 1 or end < start or end - start + 1 > MAX_PAGE_SIZE:
        raise ValueError("page window is outside the approved bounds")
    if end > MAX_PAGE_SIZE * MAX_PAGES:
        raise ValueError("page window exceeds the maximum scan bound")

    parsed = urlparse(endpoint)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query["from"] = [str(start)]
    query["to"] = [str(end)]
    flattened = [(key, value) for key, values in query.items() for value in values]
    return urlunparse(parsed._replace(query=urlencode(flattened)))


def slugify_title(title: str) -> str:
    """Match the public route style observed on ny.auksjonen.no."""
    compact = _compact(title)
    slug = re.sub(r"[^\w]+", "_", compact, flags=re.UNICODE).strip("_")
    return quote(slug, safe="_-")


def build_public_item_url(title: str, object_id: int | str) -> str:
    object_text = _compact(object_id)
    if not object_text.isdigit():
        raise ValueError("object_id must be numeric")
    slug = slugify_title(title)
    if not slug:
        raise ValueError("title must produce a non-empty public slug")
    return f"https://ny.auksjonen.no/auksjon/torget/{slug}/{object_text}"


def has_inventory_lot_signal(title: str) -> bool:
    """Return true only when the title contains explicit multi-item evidence."""
    return bool(_LOT_PATTERN.search(_compact(title)))


def _number(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _epoch_ms_to_iso(value: object) -> str | None:
    number = _number(value)
    if number is None or number <= 0:
        return None
    return datetime.fromtimestamp(number / 1000, tz=timezone.utc).isoformat()


def _is_future_epoch_ms(value: object, now: datetime) -> bool:
    number = _number(value)
    return bool(number and number / 1000 > now.timestamp())


@dataclass(frozen=True, slots=True)
class AuksjonenLiveClothingListing:
    title: str
    url: str
    auction_id: int
    object_id: int
    status: str
    listing_status: str
    current_bid_nok: float | None
    buy_now_price_nok: float | None
    start_price_nok: float | None
    bid_count: int
    bidder_count: int
    city: str | None
    zip_code: str | None
    address: str | None
    ends_at: str | None
    main_image: str | None
    inventory_lot_signal: bool
    source: str = "Auksjonen Public API"

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "auction_id": self.auction_id,
            "object_id": self.object_id,
            "status": self.status,
            "listing_status": self.listing_status,
            "current_bid_nok": self.current_bid_nok,
            "buy_now_price_nok": self.buy_now_price_nok,
            "start_price_nok": self.start_price_nok,
            "bid_count": self.bid_count,
            "bidder_count": self.bidder_count,
            "city": self.city,
            "zip_code": self.zip_code,
            "address": self.address,
            "ends_at": self.ends_at,
            "main_image": self.main_image,
            "inventory_lot_signal": self.inventory_lot_signal,
            "source": self.source,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }


def normalize_public_api_item(
    item: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> AuksjonenLiveClothingListing | None:
    """Convert one observed API object into a verified active clothing item."""
    now = now or datetime.now(timezone.utc)
    title = _compact(item.get("title"))
    if not title or not _CLOTHING_PATTERN.search(title):
        return None

    status = _compact(item.get("status")).upper()
    if status not in ACTIVE_STATUSES or bool(item.get("bidExpired")):
        return None
    if not _is_future_epoch_ms(item.get("endTime"), now):
        return None

    try:
        auction_id = int(item["auctionId"])
        object_id = int(item["objectId"])
    except (KeyError, TypeError, ValueError):
        return None

    return AuksjonenLiveClothingListing(
        title=title,
        url=build_public_item_url(title, object_id),
        auction_id=auction_id,
        object_id=object_id,
        status=status,
        listing_status="ACTIVE",
        current_bid_nok=_number(item.get("currentBidAmount")),
        buy_now_price_nok=_number(item.get("buyNowPrice")),
        start_price_nok=_number(item.get("startPrice")),
        bid_count=int(item.get("bidCount") or 0),
        bidder_count=int(item.get("bidderCount") or 0),
        city=_compact(item.get("city")) or None,
        zip_code=_compact(item.get("zipCode")) or None,
        address=_compact(item.get("address")) or None,
        ends_at=_epoch_ms_to_iso(item.get("endTime")),
        main_image=_compact(item.get("mainImage")) or None,
        inventory_lot_signal=has_inventory_lot_signal(title),
    )


@dataclass(frozen=True, slots=True)
class AuksjonenLiveClothingCollection:
    captured_at: str
    endpoint: str
    reported_size: int | None
    items_received: int
    listings: tuple[AuksjonenLiveClothingListing, ...]
    pages_fetched: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    errors: tuple[dict[str, str], ...] = ()

    @property
    def inventory_opportunities(self) -> tuple[AuksjonenLiveClothingListing, ...]:
        """Active clothing listings with explicit inventory-lot evidence only."""
        return tuple(
            listing
            for listing in self.listings
            if listing.listing_status == "ACTIVE" and listing.inventory_lot_signal
        )

    @property
    def individual_clothing_items(self) -> tuple[AuksjonenLiveClothingListing, ...]:
        """Active clothing items retained for diagnostics, never for Top 5."""
        return tuple(
            listing
            for listing in self.listings
            if listing.listing_status == "ACTIVE" and not listing.inventory_lot_signal
        )

    @property
    def scan_complete(self) -> bool:
        if self.errors or self.pages_fetched < 1:
            return False
        if self.reported_size is None:
            return self.items_received < self.pages_fetched * self.page_size
        bounded_size = min(self.reported_size, MAX_PAGES * self.page_size)
        return self.items_received >= bounded_size

    def to_dict(self) -> dict[str, Any]:
        opportunities = self.inventory_opportunities
        individuals = self.individual_clothing_items
        return {
            "schema_version": "auksjonen-live-clothing-1.2",
            "captured_at": self.captured_at,
            "endpoint": self.endpoint,
            "reported_size": self.reported_size,
            "items_received": self.items_received,
            "pages_fetched": self.pages_fetched,
            "page_size": self.page_size,
            "scan_complete": self.scan_complete,
            "active_clothing_count": len(self.listings),
            "valid_inventory_opportunity_count": len(opportunities),
            "inventory_lot_count": len(opportunities),
            "active_individual_clothing_count": len(individuals),
            "top5_count": min(5, len(opportunities)),
            "listings": [listing.to_dict() for listing in self.listings],
            "errors": list(self.errors),
            "paid_search_used": False,
            "openai_api_used": False,
            "playwright_used": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }


class AuksjonenPublicApiCollector:
    """Scan every available page in the approved public clothing category."""

    def __init__(
        self,
        endpoint: str = DEFAULT_PUBLIC_API_ENDPOINT,
        *,
        max_listings: int = MAX_LISTINGS,
        page_size: int = DEFAULT_PAGE_SIZE,
        max_pages: int = MAX_PAGES,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not is_approved_public_api_endpoint(endpoint):
            raise ValueError("endpoint is outside the approved Auksjonen clothing API")
        if not 1 <= max_listings <= MAX_LISTINGS:
            raise ValueError(f"max_listings must be between 1 and {MAX_LISTINGS}")
        if not 1 <= page_size <= MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
        if not 1 <= max_pages <= MAX_PAGES:
            raise ValueError(f"max_pages must be between 1 and {MAX_PAGES}")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.endpoint = endpoint
        self.max_listings = max_listings
        self.page_size = page_size
        self.max_pages = max_pages
        self.timeout_seconds = timeout_seconds

    def _fetch(self, url: str) -> Mapping[str, Any]:
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "OpportunityEngine/Auksjonen-Public-API-Adapter-1.2",
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            if int(response.status) != 200:
                raise RuntimeError(f"Auksjonen API returned HTTP {response.status}")
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, Mapping):
            raise RuntimeError("Auksjonen API response is not a JSON object")
        return payload

    def collect(self) -> AuksjonenLiveClothingCollection:
        captured_at = datetime.now(timezone.utc).isoformat()
        errors: list[dict[str, str]] = []
        raw_items_all: list[Mapping[str, Any]] = []
        reported_size: int | None = None
        pages_fetched = 0

        for page_index in range(self.max_pages):
            start = page_index * self.page_size + 1
            end = start + self.page_size - 1
            page_url = build_page_endpoint(self.endpoint, start, end)
            try:
                payload = self._fetch(page_url)
                raw_items = payload.get("items")
                if not isinstance(raw_items, Sequence) or isinstance(
                    raw_items, (str, bytes)
                ):
                    raise RuntimeError("Auksjonen API response lacks an items array")
            except Exception as exc:
                errors.append({"url": page_url, "error": str(exc)})
                break

            pages_fetched += 1
            raw_items_all.extend(
                item for item in raw_items if isinstance(item, Mapping)
            )

            payload_size = _positive_int(payload.get("size"))
            if reported_size is None and payload_size is not None:
                reported_size = payload_size

            if not raw_items:
                break
            if reported_size is not None and end >= reported_size:
                break
            if reported_size is None and len(raw_items) < self.page_size:
                break

        normalized_by_object_id: dict[int, AuksjonenLiveClothingListing] = {}
        for item in raw_items_all:
            listing = normalize_public_api_item(item)
            if listing is not None:
                normalized_by_object_id[listing.object_id] = listing

        normalized = list(normalized_by_object_id.values())
        normalized.sort(
            key=lambda listing: (
                not listing.inventory_lot_signal,
                listing.ends_at or "",
                listing.object_id,
            )
        )
        listings = tuple(normalized[: self.max_listings])

        return AuksjonenLiveClothingCollection(
            captured_at=captured_at,
            endpoint=self.endpoint,
            reported_size=reported_size,
            items_received=len(raw_items_all),
            listings=listings,
            pages_fetched=pages_fetched,
            page_size=self.page_size,
            errors=tuple(errors),
        )


def write_live_clothing_artifacts(
    collection: AuksjonenLiveClothingCollection,
    output_dir: str | Path,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    report_path = target / "auksjonen-live-clothing-listings.json"
    top5_path = target / "live-clothing-top5.json"
    individual_path = target / "active_individual_clothing_items.json"
    summary_path = target / "operator-summary.txt"

    report = collection.to_dict()
    opportunities = collection.inventory_opportunities
    individuals = collection.individual_clothing_items
    top5 = [listing.to_dict() for listing in opportunities[:5]]

    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    top5_path.write_text(
        json.dumps(top5, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    individual_path.write_text(
        json.dumps(
            [listing.to_dict() for listing in individuals],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    summary_lines = [
        "Auksjonen live clothing inventory adapter",
        f"Reported category size: {collection.reported_size}",
        f"Pages fetched: {collection.pages_fetched}",
        f"Page size: {collection.page_size}",
        f"Items received across all pages: {collection.items_received}",
        f"Full bounded scan complete: {collection.scan_complete}",
        f"Active clothing items: {len(collection.listings)}",
        f"Valid inventory opportunities: {len(opportunities)}",
        f"Individual clothing items excluded from Top 5: {len(individuals)}",
        f"Top 5 count: {len(top5)}",
        f"Errors: {len(collection.errors)}",
        "Paid Brave/OpenAI calls: 0",
        "",
    ]
    if opportunities:
        for listing in opportunities[:5]:
            price = listing.current_bid_nok
            summary_lines.append(
                f"- {listing.title} | {listing.city or 'unknown'} | "
                f"current bid {price if price is not None else 'unknown'} NOK | {listing.url}"
            )
    else:
        summary_lines.append("No valid inventory-lot opportunities found.")

    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    return {
        "report": report_path,
        "top5": top5_path,
        "individual_items": individual_path,
        "summary": summary_path,
    }
