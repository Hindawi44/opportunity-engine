"""Direct bounded adapter for Auksjonen's public live category API.

The endpoint and schema were observed from the public ny.auksjonen.no application.
This adapter performs one HTTPS GET, keeps active clothing-like listings only,
and builds their exact public item URLs. It uses no paid search or AI API and
never logs in, contacts a seller, bids, buys, reserves, or pays.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

DEFAULT_PUBLIC_API_ENDPOINT = (
    "https://ny.auksjonen.no/api/category-search/search"
    "?category2=10110508&from=1&to=30&asc=true&orderBy=endTime"
)
MAX_LISTINGS = 10
ACTIVE_STATUSES = frozenset({"ACTIVE", "INPROGRESS", "OPEN"})
_CLOTHING_PATTERN = re.compile(
    r"\b(klær|jakke|bukse|bukser|sko|kjole|kjoler|skjorte|skjorter|genser|gensere|"
    r"frakk|frakker|dress|dresser|vest|vester|tøy|arbeidsklær|arbeidstøy|mc-klær|"
    r"mote|tekstil|veske|vesker|overall|kjeledress|uniform)\b",
    re.I,
)
_LOT_PATTERN = re.compile(
    r"\b(vareparti|parti|restlager|lager|konkursbo|samlet|mengde|pakke|bulk)\b",
    re.I,
)


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def is_approved_public_api_endpoint(url: str) -> bool:
    parsed = urlparse(str(url or "").strip())
    return (
        parsed.scheme == "https"
        and parsed.hostname == "ny.auksjonen.no"
        and parsed.path == "/api/category-search/search"
        and "category2=10110508" in parsed.query
    )


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
    """Convert one observed API object into a verified active clothing listing."""
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
        inventory_lot_signal=bool(_LOT_PATTERN.search(title)),
    )


@dataclass(frozen=True, slots=True)
class AuksjonenLiveClothingCollection:
    captured_at: str
    endpoint: str
    reported_size: int | None
    items_received: int
    listings: tuple[AuksjonenLiveClothingListing, ...]
    errors: tuple[dict[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "auksjonen-live-clothing-1.0",
            "captured_at": self.captured_at,
            "endpoint": self.endpoint,
            "reported_size": self.reported_size,
            "items_received": self.items_received,
            "active_clothing_count": len(self.listings),
            "inventory_lot_count": sum(
                1 for listing in self.listings if listing.inventory_lot_signal
            ),
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
    """Perform one bounded public API read and return active clothing listings."""

    def __init__(
        self,
        endpoint: str = DEFAULT_PUBLIC_API_ENDPOINT,
        *,
        max_listings: int = MAX_LISTINGS,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not is_approved_public_api_endpoint(endpoint):
            raise ValueError("endpoint is outside the approved Auksjonen clothing API")
        if not 1 <= max_listings <= MAX_LISTINGS:
            raise ValueError(f"max_listings must be between 1 and {MAX_LISTINGS}")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.endpoint = endpoint
        self.max_listings = max_listings
        self.timeout_seconds = timeout_seconds

    def _fetch(self) -> Mapping[str, Any]:
        request = Request(
            self.endpoint,
            headers={
                "Accept": "application/json",
                "User-Agent": "OpportunityEngine/Auksjonen-Public-API-Adapter-1.0",
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
        payload: Mapping[str, Any] = {}
        try:
            payload = self._fetch()
            raw_items = payload.get("items")
            if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes)):
                raise RuntimeError("Auksjonen API response lacks an items array")
            normalized = [
                listing
                for item in raw_items
                if isinstance(item, Mapping)
                for listing in (normalize_public_api_item(item),)
                if listing is not None
            ]
            normalized.sort(
                key=lambda listing: (
                    not listing.inventory_lot_signal,
                    listing.ends_at or "",
                    listing.object_id,
                )
            )
            listings = tuple(normalized[: self.max_listings])
            items_received = len(raw_items)
        except Exception as exc:
            errors.append({"url": self.endpoint, "error": str(exc)})
            listings = ()
            items_received = 0

        reported_size = payload.get("size") if isinstance(payload, Mapping) else None
        try:
            reported_size = int(reported_size) if reported_size is not None else None
        except (TypeError, ValueError):
            reported_size = None
        return AuksjonenLiveClothingCollection(
            captured_at=captured_at,
            endpoint=self.endpoint,
            reported_size=reported_size,
            items_received=items_received,
            listings=listings,
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
    summary_path = target / "operator-summary.txt"
    report = collection.to_dict()
    top5 = [listing.to_dict() for listing in collection.listings[:5]]
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    top5_path.write_text(
        json.dumps(top5, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary_lines = [
        "Auksjonen live clothing adapter",
        f"Reported category size: {collection.reported_size}",
        f"Items received: {collection.items_received}",
        f"Active clothing listings: {len(collection.listings)}",
        f"Inventory-lot signals: {sum(1 for item in collection.listings if item.inventory_lot_signal)}",
        f"Errors: {len(collection.errors)}",
        "Paid Brave/OpenAI calls: 0",
        "",
    ]
    for listing in collection.listings[:5]:
        price = listing.current_bid_nok
        summary_lines.append(
            f"- {listing.title} | {listing.city or 'unknown'} | "
            f"current bid {price if price is not None else 'unknown'} NOK | {listing.url}"
        )
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    return {
        "report": report_path,
        "top5": top5_path,
        "summary": summary_path,
    }
