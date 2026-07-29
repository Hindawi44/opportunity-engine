"""Bounded multi-category Auksjonen clothing inventory collection.

The category identifiers are limited to public clothing categories observed on
ny.auksjonen.no. Each category is scanned page by page, results are de-duplicated
by objectId, and only explicit inventory-lot signals can reach opportunity output.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from opportunity_engine.discovery.auksjonen_public_api_adapter import (
    AuksjonenLiveClothingCollection,
    AuksjonenLiveClothingListing,
    DEFAULT_PAGE_SIZE,
    MAX_LISTINGS,
    MAX_PAGES,
    MAX_PAGE_SIZE,
    normalize_public_api_item,
)

API_BASE = "https://ny.auksjonen.no/api/category-search/search"


@dataclass(frozen=True, slots=True)
class AuksjonenCategorySpec:
    category_id: str
    label: str

    @property
    def endpoint(self) -> str:
        query = urlencode(
            {
                "category2": self.category_id,
                "from": 1,
                "to": DEFAULT_PAGE_SIZE,
                "asc": "true",
                "orderBy": "endTime",
            }
        )
        return f"{API_BASE}?{query}"


APPROVED_CLOTHING_CATEGORIES = (
    AuksjonenCategorySpec("10110508", "Klær, kosmetikk og accessoirer"),
    AuksjonenCategorySpec("90010", "Klær/Arbeidsklær"),
)
APPROVED_CATEGORY_IDS = frozenset(
    category.category_id for category in APPROVED_CLOTHING_CATEGORIES
)


def _nonnegative_int(value: object) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def is_approved_category_endpoint(url: str) -> bool:
    parsed = urlparse(str(url or "").strip())
    query = parse_qs(parsed.query)
    category = query.get("category2", [])
    try:
        start = int(query.get("from", [""])[0])
        end = int(query.get("to", [""])[0])
    except (TypeError, ValueError):
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname == "ny.auksjonen.no"
        and parsed.path == "/api/category-search/search"
        and len(category) == 1
        and category[0] in APPROVED_CATEGORY_IDS
        and start >= 1
        and end >= start
        and end - start + 1 <= MAX_PAGE_SIZE
        and end <= MAX_PAGE_SIZE * MAX_PAGES
    )


def build_category_page_endpoint(
    category: AuksjonenCategorySpec,
    start: int,
    end: int,
) -> str:
    if category.category_id not in APPROVED_CATEGORY_IDS:
        raise ValueError("category is outside the approved Auksjonen clothing set")
    if start < 1 or end < start or end - start + 1 > MAX_PAGE_SIZE:
        raise ValueError("page window is outside the approved bounds")
    if end > MAX_PAGE_SIZE * MAX_PAGES:
        raise ValueError("page window exceeds the maximum scan bound")

    parsed = urlparse(category.endpoint)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query["from"] = [str(start)]
    query["to"] = [str(end)]
    flattened = [(key, value) for key, values in query.items() for value in values]
    endpoint = urlunparse(parsed._replace(query=urlencode(flattened)))
    if not is_approved_category_endpoint(endpoint):
        raise ValueError("generated endpoint failed the approved category gate")
    return endpoint


@dataclass(frozen=True, slots=True)
class AuksjonenCategoryScan:
    category: AuksjonenCategorySpec
    reported_size: int | None
    items_received: int
    pages_fetched: int
    page_size: int
    max_pages: int
    listings: tuple[AuksjonenLiveClothingListing, ...]
    errors: tuple[dict[str, str], ...] = ()

    @property
    def scan_complete(self) -> bool:
        if self.errors or self.pages_fetched < 1:
            return False
        if self.reported_size is None:
            return self.items_received < self.pages_fetched * self.page_size
        bounded_size = min(self.reported_size, self.max_pages * self.page_size)
        return self.items_received >= bounded_size

    def to_dict(self) -> dict[str, Any]:
        return {
            "category_id": self.category.category_id,
            "category_label": self.category.label,
            "endpoint": self.category.endpoint,
            "reported_size": self.reported_size,
            "items_received": self.items_received,
            "pages_fetched": self.pages_fetched,
            "page_size": self.page_size,
            "max_pages": self.max_pages,
            "scan_complete": self.scan_complete,
            "active_clothing_count": len(self.listings),
            "inventory_lot_count": sum(
                1 for listing in self.listings if listing.inventory_lot_signal
            ),
            "errors": list(self.errors),
        }


@dataclass(frozen=True, slots=True)
class AuksjonenMultiCategoryResult:
    captured_at: str
    scans: tuple[AuksjonenCategoryScan, ...]
    max_listings: int

    @property
    def scan_complete(self) -> bool:
        return bool(self.scans) and all(scan.scan_complete for scan in self.scans)

    @property
    def combined(self) -> AuksjonenLiveClothingCollection:
        by_object_id: dict[int, AuksjonenLiveClothingListing] = {}
        errors: list[dict[str, str]] = []
        reported_sizes: list[int] = []

        for scan in self.scans:
            for listing in scan.listings:
                by_object_id[listing.object_id] = listing
            errors.extend(scan.errors)
            if not scan.scan_complete and not scan.errors:
                errors.append(
                    {
                        "url": scan.category.endpoint,
                        "error": "bounded category scan incomplete",
                    }
                )
            if scan.reported_size is not None:
                reported_sizes.append(scan.reported_size)

        listings = list(by_object_id.values())
        listings.sort(
            key=lambda listing: (
                not listing.inventory_lot_signal,
                listing.ends_at or "",
                listing.object_id,
            )
        )
        all_sizes_known = len(reported_sizes) == len(self.scans)
        return AuksjonenLiveClothingCollection(
            captured_at=self.captured_at,
            endpoint=" | ".join(scan.category.endpoint for scan in self.scans),
            reported_size=sum(reported_sizes) if all_sizes_known else None,
            items_received=sum(scan.items_received for scan in self.scans),
            listings=tuple(listings[: self.max_listings]),
            pages_fetched=sum(scan.pages_fetched for scan in self.scans),
            page_size=self.scans[0].page_size if self.scans else DEFAULT_PAGE_SIZE,
            errors=tuple(errors),
        )

    def to_dict(self) -> dict[str, Any]:
        combined = self.combined
        return {
            "schema_version": "auksjonen-multi-category-1.0",
            "captured_at": self.captured_at,
            "category_count": len(self.scans),
            "scan_complete": self.scan_complete,
            "categories": [scan.to_dict() for scan in self.scans],
            "combined": {
                "reported_size": combined.reported_size,
                "items_received": combined.items_received,
                "pages_fetched": combined.pages_fetched,
                "active_clothing_count": len(combined.listings),
                "valid_inventory_opportunity_count": len(
                    combined.inventory_opportunities
                ),
                "top5_count": min(5, len(combined.inventory_opportunities)),
                "errors": list(combined.errors),
            },
            "paid_search_used": False,
            "openai_api_used": False,
            "playwright_used": False,
        }


class AuksjonenMultiCategoryCollector:
    """Scan the approved Auksjonen clothing categories within fixed bounds."""

    def __init__(
        self,
        *,
        categories: Sequence[AuksjonenCategorySpec] = APPROVED_CLOTHING_CATEGORIES,
        max_listings: int = MAX_LISTINGS,
        page_size: int = DEFAULT_PAGE_SIZE,
        max_pages: int = MAX_PAGES,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not categories:
            raise ValueError("at least one approved category is required")
        if any(category.category_id not in APPROVED_CATEGORY_IDS for category in categories):
            raise ValueError("categories contain an unapproved Auksjonen category")
        if not 1 <= max_listings <= MAX_LISTINGS:
            raise ValueError(f"max_listings must be between 1 and {MAX_LISTINGS}")
        if not 1 <= page_size <= MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
        if not 1 <= max_pages <= MAX_PAGES:
            raise ValueError(f"max_pages must be between 1 and {MAX_PAGES}")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.categories = tuple(categories)
        self.max_listings = max_listings
        self.page_size = page_size
        self.max_pages = max_pages
        self.timeout_seconds = timeout_seconds

    def _fetch(self, url: str) -> Mapping[str, Any]:
        if not is_approved_category_endpoint(url):
            raise ValueError("endpoint is outside the approved category gate")
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "OpportunityEngine/Auksjonen-Multi-Category-1.0",
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            if int(response.status) != 200:
                raise RuntimeError(f"Auksjonen API returned HTTP {response.status}")
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, Mapping):
            raise RuntimeError("Auksjonen API response is not a JSON object")
        return payload

    def _collect_category(self, category: AuksjonenCategorySpec) -> AuksjonenCategoryScan:
        raw_items_all: list[Mapping[str, Any]] = []
        errors: list[dict[str, str]] = []
        reported_size: int | None = None
        pages_fetched = 0

        for page_index in range(self.max_pages):
            start = page_index * self.page_size + 1
            end = start + self.page_size - 1
            page_url = build_category_page_endpoint(category, start, end)
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
            payload_size = _nonnegative_int(payload.get("size"))
            if reported_size is None and payload_size is not None:
                reported_size = payload_size

            if not raw_items:
                break
            if reported_size is not None and end >= reported_size:
                break
            if reported_size is None and len(raw_items) < self.page_size:
                break

        by_object_id: dict[int, AuksjonenLiveClothingListing] = {}
        now = datetime.now(timezone.utc)
        for item in raw_items_all:
            listing = normalize_public_api_item(item, now=now)
            if listing is not None:
                by_object_id[listing.object_id] = listing
        listings = list(by_object_id.values())
        listings.sort(
            key=lambda listing: (
                not listing.inventory_lot_signal,
                listing.ends_at or "",
                listing.object_id,
            )
        )
        return AuksjonenCategoryScan(
            category=category,
            reported_size=reported_size,
            items_received=len(raw_items_all),
            pages_fetched=pages_fetched,
            page_size=self.page_size,
            max_pages=self.max_pages,
            listings=tuple(listings),
            errors=tuple(errors),
        )

    def collect(self) -> AuksjonenMultiCategoryResult:
        captured_at = datetime.now(timezone.utc).isoformat()
        scans = tuple(self._collect_category(category) for category in self.categories)
        return AuksjonenMultiCategoryResult(
            captured_at=captured_at,
            scans=scans,
            max_listings=self.max_listings,
        )


def write_multi_category_artifact(
    result: AuksjonenMultiCategoryResult,
    output_dir: str | Path,
) -> Path:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / "auksjonen-category-scans.json"
    path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path
