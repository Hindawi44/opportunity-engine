"""Authorized, bounded Playwright pilot for FINN Clothing Inventory discovery.

FINN's public robots notice requires explicit written permission for automated
collection.  This adapter therefore fails closed unless the operator supplies a
written-permission reference.  It never logs in, bypasses access controls,
contacts sellers, or performs a commercial action.

The browser is only a replaceable collection adapter.  Rendered pages are
verified by the existing Clothing Inventory verifier and then passed through the
existing Discovery Engine.  The Opportunity Dossier and Analysis Engine remain
unchanged.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from opportunity_engine.discovery.clothing_inventory_search import (
    UNKNOWN,
    DiscoveryQuery,
    PageVerification,
    normalize_public_url,
    run_clothing_inventory_discovery,
    verify_public_html,
    write_discovery_artifacts,
)
from opportunity_engine.discovery.early_opportunity_gate import (
    apply_early_opportunity_gate,
)
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.source_channel_guard import (
    enforce_source_channel_identity,
)

DEFAULT_FINN_SEARCH_URL = (
    "https://www.finn.no/recommerce/forsale/search"
    "?product_category=2.91.3108.363"
)
MIN_LISTINGS = 20
MAX_LISTINGS = 50
MIN_DELAY_SECONDS = 2.0
MAX_SEARCH_PAGES = 3
_BATCH_SIZE = 20
_FINN_HOSTS = {"finn.no", "www.finn.no"}
_FINN_ITEM_PATHS = (
    "/recommerce/forsale/item/",
    "/bap/forsale/ad.html",
)
_FINN_SEARCH_PATHS = (
    "/recommerce/forsale/search",
    "/bap/forsale/search.html",
)
_IMAGE_LIMIT = 12


@dataclass(frozen=True, slots=True)
class FinnPlaywrightPilotConfig:
    """Safety and volume limits for one manually initiated pilot run."""

    written_permission_reference: str
    search_urls: tuple[str, ...] = (DEFAULT_FINN_SEARCH_URL,)
    max_listings: int = MIN_LISTINGS
    max_search_pages: int = 1
    delay_seconds: float = 3.0
    navigation_timeout_seconds: float = 30.0
    headless: bool = True

    def __post_init__(self) -> None:
        if not self.written_permission_reference.strip():
            raise ValueError(
                "FINN written automation permission reference is required"
            )
        if not MIN_LISTINGS <= self.max_listings <= MAX_LISTINGS:
            raise ValueError(
                f"max_listings must be between {MIN_LISTINGS} and {MAX_LISTINGS}"
            )
        if not 1 <= self.max_search_pages <= MAX_SEARCH_PAGES:
            raise ValueError(
                f"max_search_pages must be between 1 and {MAX_SEARCH_PAGES}"
            )
        if self.delay_seconds < MIN_DELAY_SECONDS:
            raise ValueError(
                f"delay_seconds must be at least {MIN_DELAY_SECONDS:g}"
            )
        if self.navigation_timeout_seconds <= 0:
            raise ValueError("navigation_timeout_seconds must be positive")
        if not self.search_urls:
            raise ValueError("at least one FINN search URL is required")
        for url in self.search_urls:
            _validate_finn_search_url(url)


@dataclass(frozen=True, slots=True)
class FinnPilotListing:
    """One public FINN listing captured by the bounded browser pilot."""

    listing_id: str
    title: str
    url: str
    description: str
    price_nok: float | None
    location: str | None
    image_urls: tuple[str, ...]
    listing_status: str
    captured_at: str
    search_url: str
    verification: PageVerification

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["image_urls"] = list(self.image_urls)
        value["verification"] = self.verification.to_dict()
        return value


@dataclass(frozen=True, slots=True)
class FinnPlaywrightCollection:
    """Network collection result retained separately from commercial analysis."""

    captured_at: str
    listings: tuple[FinnPilotListing, ...]
    search_urls: tuple[str, ...]
    network_pages_visited: int
    delay_seconds: float
    max_listings: int
    permission_reference_present: bool = True
    errors: tuple[dict[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "finn-playwright-clothing-pilot-1.0",
            "domain": "CLOTHING_INVENTORY",
            "source": "FINN.no",
            "collection_mode": "AUTHORIZED_PLAYWRIGHT_PILOT",
            "captured_at": self.captured_at,
            "search_urls": list(self.search_urls),
            "network_pages_visited": self.network_pages_visited,
            "delay_seconds": self.delay_seconds,
            "max_listings": self.max_listings,
            "permission_reference_present": self.permission_reference_present,
            "listings": [listing.to_dict() for listing in self.listings],
            "errors": list(self.errors),
            "automatic_contact": False,
            "automatic_purchase_decision": False,
            "automatic_bid": False,
            "automatic_reservation": False,
            "automatic_payment": False,
        }


def _validate_finn_search_url(url: str) -> None:
    parsed = urlparse(url.strip())
    if (
        parsed.scheme.lower() != "https"
        or parsed.netloc.lower() not in _FINN_HOSTS
        or parsed.path.lower() not in _FINN_SEARCH_PATHS
    ):
        raise ValueError(
            "search URL must be a public HTTPS FINN Torget search page"
        )


def _valid_finn_item_url(url: str) -> str:
    canonical = normalize_public_url(url)
    parsed = urlparse(canonical)
    if (
        not canonical
        or parsed.netloc.lower() not in {"finn.no"}
        or not any(path in parsed.path.lower() for path in _FINN_ITEM_PATHS)
    ):
        return ""
    if "/bap/forsale/ad.html" in parsed.path.lower():
        params = dict(parse_qsl(parsed.query, keep_blank_values=True))
        if not str(params.get("finnkode") or "").isdigit():
            return ""
    return canonical


def _with_page_number(url: str, page_number: int) -> str:
    parsed = urlparse(url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if page_number > 1:
        params["page"] = str(page_number)
    else:
        params.pop("page", None)
    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        "",
        urlencode(sorted(params.items())),
        "",
    ))


def _listing_id(url: str) -> str:
    parsed = urlparse(url)
    match = re.search(r"/item/(\d+)(?:$|/)", parsed.path)
    if match:
        return match.group(1)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    finnkode = str(params.get("finnkode") or "")
    if finnkode.isdigit():
        return finnkode
    raise ValueError("FINN item URL does not contain a stable listing ID")


def _normalize_image_urls(values: Iterable[object]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        url = str(value or "").strip()
        parsed = urlparse(url)
        if (
            parsed.scheme.lower() != "https"
            or not parsed.netloc
            or url in normalized
        ):
            continue
        normalized.append(url)
        if len(normalized) >= _IMAGE_LIMIT:
            break
    return tuple(normalized)


def normalize_search_cards(
    rows: Iterable[Mapping[str, Any]],
    *,
    search_url: str,
) -> list[dict[str, Any]]:
    """Normalize browser-extracted search cards without inventing fields."""
    normalized: dict[str, dict[str, Any]] = {}
    for row in rows:
        url = _valid_finn_item_url(str(row.get("url") or ""))
        title = " ".join(str(row.get("title") or "").split())
        description = " ".join(str(row.get("description") or "").split())
        if not url or not title:
            continue
        listing_id = _listing_id(url)
        normalized.setdefault(listing_id, {
            "listing_id": listing_id,
            "title": title,
            "url": url,
            "description": description[:4000],
            "image_urls": _normalize_image_urls(row.get("image_urls") or ()),
            "search_url": search_url,
        })
    return list(normalized.values())


def _extract_search_cards(page: Any, *, search_url: str) -> list[dict[str, Any]]:
    rows = page.locator(
        'a[href*="/recommerce/forsale/item/"], '
        'a[href*="/bap/forsale/ad.html"]'
    ).evaluate_all(
        """anchors => anchors.map(anchor => {
          const card = anchor.closest(
            'article, li, [data-testid*="result"], [data-testid*="ad"], [class*="card"]'
          ) || anchor.parentElement;
          const heading = anchor.querySelector('h1,h2,h3')
            || card?.querySelector('h1,h2,h3');
          const images = [...(card?.querySelectorAll('img') || [])]
            .map(image => image.currentSrc || image.src)
            .filter(Boolean);
          return {
            url: anchor.href,
            title: (heading?.innerText || anchor.getAttribute('aria-label')
              || anchor.innerText || '').trim(),
            description: (card?.innerText || anchor.innerText || '').trim(),
            image_urls: images,
          };
        })"""
    )
    return normalize_search_cards(rows, search_url=search_url)


def _extract_detail_page(page: Any) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const meta = (selector) =>
            document.querySelector(selector)?.getAttribute('content') || '';
          const main = document.querySelector('main') || document.body;
          const descriptionNode = document.querySelector(
            '[data-testid*="description"], article [class*="description"], main article'
          );
          const title = meta('meta[property="og:title"]')
            || document.querySelector('h1')?.innerText
            || document.title
            || '';
          const description = meta('meta[name="description"]')
            || meta('meta[property="og:description"]')
            || descriptionNode?.innerText
            || main?.innerText
            || '';
          const imageUrls = [
            meta('meta[property="og:image"]'),
            ...[...(main?.querySelectorAll('img') || [])]
              .map(image => image.currentSrc || image.src),
          ].filter(Boolean);
          return {
            title: title.trim(),
            description: description.trim(),
            image_urls: imageUrls,
          };
        }"""
    )


class FinnPlaywrightPilotAdapter:
    """Collect a small authorized FINN sample in a real Chromium browser."""

    def __init__(self, config: FinnPlaywrightPilotConfig) -> None:
        self.config = config

    def collect(self) -> FinnPlaywrightCollection:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - depends on optional install
            raise RuntimeError(
                "Playwright is not installed; run "
                "`python -m pip install -r requirements-playwright.txt` and "
                "`python -m playwright install chromium`"
            ) from exc

        captured_at = datetime.now(timezone.utc).isoformat()
        search_cards: dict[str, dict[str, Any]] = {}
        listings: list[FinnPilotListing] = []
        errors: list[dict[str, str]] = []
        pages_visited = 0

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.config.headless)
            context = browser.new_context(
                user_agent="OpportunityEngine/FINN-Authorized-Pilot-1.0"
            )
            page = context.new_page()
            page.set_default_navigation_timeout(
                self.config.navigation_timeout_seconds * 1000
            )

            for base_url in self.config.search_urls:
                for page_number in range(1, self.config.max_search_pages + 1):
                    if len(search_cards) >= self.config.max_listings:
                        break
                    target_url = _with_page_number(base_url, page_number)
                    if pages_visited:
                        page.wait_for_timeout(self.config.delay_seconds * 1000)
                    try:
                        page.goto(target_url, wait_until="domcontentloaded")
                        pages_visited += 1
                        page.wait_for_timeout(self.config.delay_seconds * 1000)
                        for card in _extract_search_cards(
                            page,
                            search_url=target_url,
                        ):
                            search_cards.setdefault(card["listing_id"], card)
                            if len(search_cards) >= self.config.max_listings:
                                break
                    except Exception as exc:
                        errors.append({
                            "url": target_url,
                            "stage": "search_page",
                            "error": str(exc),
                        })

            for card in list(search_cards.values())[: self.config.max_listings]:
                page.wait_for_timeout(self.config.delay_seconds * 1000)
                try:
                    page.goto(card["url"], wait_until="domcontentloaded")
                    pages_visited += 1
                    page.wait_for_timeout(self.config.delay_seconds * 1000)
                    final_url = _valid_finn_item_url(page.url) or card["url"]
                    detail = _extract_detail_page(page)
                    rendered_html = page.content()
                    verification = enforce_source_channel_identity(
                        verify_public_html(final_url, rendered_html)
                    )
                    title = " ".join(
                        str(detail.get("title") or card["title"]).split()
                    )
                    description = " ".join(
                        str(
                            detail.get("description")
                            or card["description"]
                            or ""
                        ).split()
                    )[:4000]
                    image_urls = _normalize_image_urls((
                        *(detail.get("image_urls") or ()),
                        *(card.get("image_urls") or ()),
                    ))
                except Exception as exc:
                    errors.append({
                        "url": card["url"],
                        "stage": "detail_page",
                        "error": str(exc),
                    })
                    final_url = card["url"]
                    title = card["title"]
                    description = card["description"]
                    image_urls = tuple(card["image_urls"])
                    verification = PageVerification(
                        url=final_url,
                        listing_status=UNKNOWN,
                        verified=False,
                        error=str(exc),
                    )

                listings.append(FinnPilotListing(
                    listing_id=card["listing_id"],
                    title=title,
                    url=final_url,
                    description=description,
                    price_nok=verification.price_nok,
                    location=verification.location,
                    image_urls=image_urls,
                    listing_status=verification.listing_status,
                    captured_at=captured_at,
                    search_url=card["search_url"],
                    verification=verification,
                ))
            context.close()
            browser.close()

        return FinnPlaywrightCollection(
            captured_at=captured_at,
            listings=tuple(listings),
            search_urls=self.config.search_urls,
            network_pages_visited=pages_visited,
            delay_seconds=self.config.delay_seconds,
            max_listings=self.config.max_listings,
            errors=tuple(errors),
        )


class _CollectedFinnProvider:
    name = "FINN Playwright Pilot"

    def __init__(self, batches: Mapping[str, Sequence[SearchHit]]) -> None:
        self._batches = dict(batches)

    def search(self, query: str, *, count: int = _BATCH_SIZE) -> Sequence[SearchHit]:
        return self._batches.get(query, ())[:count]


def _build_batches(
    collection: FinnPlaywrightCollection,
) -> tuple[_CollectedFinnProvider, tuple[DiscoveryQuery, ...]]:
    batches: dict[str, tuple[SearchHit, ...]] = {}
    queries: list[DiscoveryQuery] = []
    listings = collection.listings[:MAX_LISTINGS]
    for offset in range(0, len(listings), _BATCH_SIZE):
        batch_number = (offset // _BATCH_SIZE) + 1
        query_text = f"authorized-finn-playwright-pilot-batch-{batch_number}"
        batch = listings[offset: offset + _BATCH_SIZE]
        batches[query_text] = tuple(
            SearchHit(
                title=listing.title,
                url=listing.url,
                description=listing.description,
                provider="FINN Playwright Pilot",
            )
            for listing in batch
        )
        queries.append(DiscoveryQuery(
            query_id=f"finn-pilot-{batch_number:02d}",
            scenario="LARGE_LOT_SALE",
            intent="SALE_INTENT",
            asset_scope="CLOTHING_INVENTORY",
            query=query_text,
            rotation_group="AUTHORIZED_PILOT",
        ))
    return _CollectedFinnProvider(batches), tuple(queries)


def _attach_capture_evidence(
    result: dict[str, Any],
    collection: FinnPlaywrightCollection,
) -> None:
    by_url = {
        normalize_public_url(listing.url): listing
        for listing in collection.listings
    }
    for output_name in (
        "all_discovered_candidates",
        "discovery_top5",
    ):
        for candidate in result[output_name]:
            matched = [
                by_url[normalize_public_url(url)]
                for url in candidate.get("source_urls") or ()
                if normalize_public_url(url) in by_url
            ]
            candidate["image_urls"] = list(dict.fromkeys(
                image
                for listing in matched
                for image in listing.image_urls
            ))
            candidate["source_capture"] = [
                {
                    "provider": "FINN Playwright Pilot",
                    "listing_id": listing.listing_id,
                    "captured_at": listing.captured_at,
                    "search_url": listing.search_url,
                }
                for listing in matched
            ]


def run_finn_playwright_pilot(
    collection: FinnPlaywrightCollection,
) -> dict[str, Any]:
    """Pass one authorized collection through the existing Discovery Engine."""
    provider, queries = _build_batches(collection)
    verification_by_url = {
        normalize_public_url(listing.url): listing.verification
        for listing in collection.listings
    }

    def verifier(url: str) -> PageVerification:
        return verification_by_url.get(
            normalize_public_url(url),
            PageVerification(
                url=url,
                verified=False,
                error="listing was not captured by the authorized pilot",
            ),
        )

    raw_result = run_clothing_inventory_discovery(
        provider,
        queries=queries,
        discovered_at=collection.captured_at,
        results_per_query=_BATCH_SIZE,
        verifier=verifier,
        verification_limit=len(collection.listings),
    )
    result = apply_early_opportunity_gate(raw_result)
    _attach_capture_evidence(result, collection)
    report = result["search_run_report"]
    report.update({
        "collection_mode": "AUTHORIZED_FINN_PLAYWRIGHT_PILOT",
        "collection_schema_version": "finn-playwright-clothing-pilot-1.0",
        "network_listings_collected": len(collection.listings),
        "network_pages_visited": collection.network_pages_visited,
        "network_listing_limit": collection.max_listings,
        "delay_seconds": collection.delay_seconds,
        "permission_reference_present": collection.permission_reference_present,
        "collection_errors": list(collection.errors),
        "automatic_contact": False,
        "automatic_purchase_decision": False,
        "financial_ranking_used": False,
    })
    return result


def write_finn_playwright_pilot_artifacts(
    result: Mapping[str, Any],
    collection: FinnPlaywrightCollection,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Write the existing discovery artifacts plus the raw pilot evidence."""
    paths = write_discovery_artifacts(result, output_dir)
    collection_path = Path(output_dir) / "finn-playwright-collection.json"
    collection_path.write_text(
        json.dumps(collection.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths["finn_playwright_collection"] = collection_path
    return paths
