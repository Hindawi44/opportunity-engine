"""Compatibility helpers for current public Riegermann catalog markup.

The fixture-first parser remains unchanged. This module broadens only the live
catalog link shape (relative or absolute), follows bounded public catalog
pagination, and creates conservative child evidence when the public catalog
does not wrap items in fixture-style articles.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, replace
from typing import Any
from urllib.parse import parse_qs, unquote, urljoin, urlparse, urlunparse

from opportunity_engine.discovery import germany_riegermann as fixture_parser
from opportunity_engine.discovery import germany_riegermann_live as live_layer
from opportunity_engine.discovery.germany_riegermann import (
    RiegermannAuctionEvent,
    RiegermannChildLot,
    canonicalize_riegermann_url,
)

_ITEM_LINK_RE = re.compile(
    r"href\s*=\s*[\"']"
    r"(?:https?://(?:www\.)?riegermann\.de)?"
    r"(?P<href>/de/l/(?P<object_id>[0-9]+)/[^\"'?#]+)"
    r"(?:\?[^\"']*)?[\"']",
    re.I,
)
_HREF_RE = re.compile(r"href\s*=\s*[\"'](?P<href>[^\"']+)[\"']", re.I)
_CLOTHING_TERMS = (
    "bekleidung",
    "kleidung",
    "lederjacke",
    "ledermantel",
    "jacke",
    "mantel",
    "hose",
    "kleid",
    "rock",
    "schuhe",
    "stiefel",
    "bluse",
    "pullover",
    "mode",
)
_BULK_TERMS = (
    "posten",
    "konvolut",
    "sortiment",
    "warenbestand",
    "lagerbestand",
    "restposten",
    "paket",
)
_QUANTITY_RE = re.compile(
    r"\b(?P<count>[0-9]{1,7})\s*"
    r"(?:stück|stueck|stk|teile|jacken|mäntel|maentel|hosen|kleider|paar|artikel)\b",
    re.I,
)
_LOCATION_RE = re.compile(
    r"\b(?P<location>DE-[0-9]{5}\s+.+?)"
    r"(?=\s+(?:Zuschläge|Gebotsabgabe|Aktuell|Vorschau|Nachverkauf|"
    r"Abgeschlossen|Terminauktion)\b|$)",
    re.I,
)
_PERCENT_RE = re.compile(
    r"(?:{labels})\s*:?\s*(?P<value>[0-9]+(?:[.,][0-9]+)?)\s*%",
    re.I,
)

_ORIGINAL_RUN_RIEGERMANN_LIVE_DISCOVERY = live_layer.run_riegermann_live_discovery
_ORIGINAL_MERGE_INFORMATION_EVENT = live_layer._merge_information_event


def extract_riegermann_item_urls_compat(
    catalog_url: str,
    source_html: str,
    *,
    limit: int = 10_000,
) -> tuple[str, ...]:
    """Extract relative or absolute exact Riegermann item links."""
    if limit < 1:
        raise ValueError("limit must be positive")
    identity = canonicalize_riegermann_url(catalog_url)
    if identity is None or identity.kind != "AUCTION_CATALOG":
        raise ValueError("catalog_url must be an exact Riegermann auction catalog")

    urls: list[str] = []
    seen: set[str] = set()
    for match in _ITEM_LINK_RE.finditer(source_html):
        candidate = urljoin("https://www.riegermann.de", match.group("href"))
        parsed = canonicalize_riegermann_url(candidate)
        if parsed is None or parsed.kind != "ITEM_DETAIL":
            continue
        if parsed.canonical_url in seen:
            continue
        seen.add(parsed.canonical_url)
        urls.append(parsed.canonical_url)
        if len(urls) >= limit:
            break
    return tuple(urls)


def _catalog_offset(url: str) -> int:
    values = parse_qs(urlparse(url).query).get("currentpos")
    if not values:
        return 0
    try:
        value = int(values[-1])
    except (TypeError, ValueError):
        return 0
    return max(value, 0)


def extract_riegermann_catalog_page_urls_compat(
    catalog_url: str,
    source_html: str,
) -> tuple[str, ...]:
    """Return one same-auction public pagination URL for each catalog offset."""
    identity = canonicalize_riegermann_url(catalog_url)
    if identity is None or identity.kind != "AUCTION_CATALOG":
        raise ValueError("catalog_url must be an exact Riegermann auction catalog")

    current_offset = _catalog_offset(catalog_url)
    by_offset: dict[int, str] = {}
    for match in _HREF_RE.finditer(source_html):
        href = re.sub(
            r"&(?:amp|#38|#x26);",
            "&",
            match.group("href"),
            flags=re.I,
        ).strip()
        if not href:
            continue
        candidate = urljoin(catalog_url, href)
        candidate_identity = canonicalize_riegermann_url(candidate)
        if (
            candidate_identity is None
            or candidate_identity.kind != "AUCTION_CATALOG"
            or candidate_identity.auction_id != identity.auction_id
        ):
            continue
        parsed = urlparse(candidate)
        currentpos = parse_qs(parsed.query).get("currentpos")
        if not currentpos:
            continue
        try:
            offset = int(currentpos[-1])
        except (TypeError, ValueError):
            continue
        if offset < 0 or offset == current_offset:
            continue
        normalized = urlunparse(
            (
                "https",
                "riegermann.de",
                parsed.path,
                "",
                parsed.query,
                "",
            )
        )
        by_offset.setdefault(offset, normalized)
    return tuple(by_offset[offset] for offset in sorted(by_offset))


def _visible_text(source_html: str) -> str:
    source = re.sub(
        r"<(script|style|noscript)\b[^>]*>.*?</\1>",
        " ",
        source_html,
        flags=re.I | re.S,
    )
    source = re.sub(r"<[^>]+>", " ", source)
    return " ".join(html.unescape(source).split())


def _source_percent(text: str, labels: tuple[str, ...]) -> float | None:
    pattern = _PERCENT_RE.pattern.format(
        labels="|".join(re.escape(label) for label in labels)
    )
    match = re.search(pattern, text, flags=re.I)
    if not match:
        return None
    try:
        return float(match.group("value").replace(",", "."))
    except ValueError:
        return None


def _apply_metadata_fallbacks(
    event: RiegermannAuctionEvent,
    source_html: str,
) -> RiegermannAuctionEvent:
    visible = _visible_text(source_html)
    location = event.location
    if location is None:
        location_match = _LOCATION_RE.search(visible)
        if location_match:
            location = " ".join(location_match.group("location").split())

    buyer_premium = event.buyer_premium_percent
    if buyer_premium is None:
        buyer_premium = _source_percent(visible, ("Aufgeld", "Käuferaufgeld"))

    vat = event.vat_percent
    if vat is None:
        vat = _source_percent(visible, ("USt", "MwSt", "Mehrwertsteuer"))

    if (
        location == event.location
        and buyer_premium == event.buyer_premium_percent
        and vat == event.vat_percent
    ):
        return event
    return replace(
        event,
        location=location,
        buyer_premium_percent=buyer_premium,
        vat_percent=vat,
    )


def _fallback_lot(
    item_url: str,
    *,
    auction_id: str,
    listing_status: str,
) -> RiegermannChildLot:
    identity = canonicalize_riegermann_url(item_url)
    if identity is None or identity.object_id is None:
        raise ValueError("item_url must be an exact Riegermann item page")
    slug = unquote(urlparse(identity.canonical_url).path.rstrip("/").split("/")[-1])
    title = " ".join(slug.replace("_", " ").replace("-", " ").split()).title()
    normalized = title.casefold()
    quantity_match = _QUANTITY_RE.search(normalized)
    quantity = int(quantity_match.group("count")) if quantity_match else None
    clothing = any(term in normalized for term in _CLOTHING_TERMS)
    bulk = any(term in normalized for term in _BULK_TERMS) or (
        quantity is not None and quantity >= 2
    )
    return RiegermannChildLot(
        auction_id=auction_id,
        object_id=identity.object_id,
        canonical_url=identity.canonical_url,
        lot_number=None,
        title=title or f"Riegermann object {identity.object_id}",
        description=None,
        listing_status=listing_status,
        quantity=quantity,
        clothing_evidence=clothing,
        bulk_evidence=bulk,
        ordinary_single_garment=clothing and not bulk,
        promotion_eligible=clothing and bulk,
        top5_eligible=False,
        source_price_kind=None,
        source_start_or_minimum_price_eur=None,
        source_displayed_bid_eur=None,
        source_bid_count=None,
        final_sale_price_eur=None,
        final_sale_price_trusted=False,
    )


def parse_riegermann_catalog_html_compat(
    url: str,
    source_html: str,
) -> RiegermannAuctionEvent:
    """Parse fixture-style cards and conservatively retain missing catalog links."""
    event = _apply_metadata_fallbacks(
        fixture_parser.parse_riegermann_catalog_html(url, source_html),
        source_html,
    )
    page_identity = canonicalize_riegermann_url(url)
    if page_identity is None or page_identity.kind != "AUCTION_CATALOG":
        return event

    item_urls = extract_riegermann_item_urls_compat(url, source_html)
    known = {lot.object_id for lot in event.child_lots}
    fallback = [
        _fallback_lot(
            item_url,
            auction_id=event.auction_id,
            listing_status=event.listing_status,
        )
        for item_url in item_urls
        if (
            (identity := canonicalize_riegermann_url(item_url)) is not None
            and identity.object_id is not None
            and identity.object_id not in known
        )
    ]
    if not fallback:
        return event
    return replace(event, child_lots=(*event.child_lots, *fallback))


def _merge_information_event_compat(
    catalog_event: RiegermannAuctionEvent,
    information_event: RiegermannAuctionEvent,
) -> RiegermannAuctionEvent:
    """Merge parent metadata and propagate a changed parent fallback status to lots."""
    merged = _ORIGINAL_MERGE_INFORMATION_EVENT(catalog_event, information_event)
    if merged.listing_status == catalog_event.listing_status:
        return merged
    return replace(
        merged,
        child_lots=tuple(
            replace(lot, listing_status=merged.listing_status)
            if lot.listing_status == catalog_event.listing_status
            else lot
            for lot in merged.child_lots
        ),
    )


@dataclass
class _MergedResponse:
    url: str
    content: bytes
    status_code: int = 200
    content_type: str = "text/html; charset=utf-8"
    encoding: str | None = "utf-8"

    def __post_init__(self) -> None:
        self.headers = {"content-type": self.content_type}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _PaginatedCatalogSession:
    def __init__(
        self,
        catalog_url: str,
        *,
        upstream: Any,
        timeout: float,
        max_response_bytes: int,
        page_limit: int,
    ) -> None:
        identity = canonicalize_riegermann_url(catalog_url)
        if identity is None or identity.kind != "AUCTION_CATALOG":
            raise ValueError("catalog_url must be an exact Riegermann auction catalog")
        self.catalog_url = catalog_url
        self.auction_id = identity.auction_id
        self.upstream = upstream
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self.page_limit = page_limit
        self.catalog_page_urls: list[str] = []
        self.catalog_page_errors: list[dict[str, str]] = []
        self.catalog_coverage_complete = False
        self.catalog_limit_reached = False
        self._merged_response: _MergedResponse | None = None

    def get(self, url: str, **kwargs: Any) -> Any:
        identity = canonicalize_riegermann_url(url)
        if (
            identity is not None
            and identity.kind == "AUCTION_CATALOG"
            and identity.auction_id == self.auction_id
        ):
            if self._merged_response is None:
                self._merged_response = self._load_catalog()
            return self._merged_response
        return self.upstream.get(url, **kwargs)

    def _fetch_page(self, url: str) -> live_layer.RiegermannPublicPage:
        return live_layer.fetch_riegermann_public_page(
            url,
            session=self.upstream,
            timeout=self.timeout,
            max_response_bytes=self.max_response_bytes,
        )

    def _load_catalog(self) -> _MergedResponse:
        first = self._fetch_page(self.catalog_url)
        self.catalog_page_urls.append(first.requested_url)

        item_urls = list(
            extract_riegermann_item_urls_compat(first.canonical_url, first.html)
        )
        seen_items = set(item_urls)
        visited_offsets = {_catalog_offset(self.catalog_url)}
        queued_by_offset: dict[int, str] = {
            _catalog_offset(url): url
            for url in extract_riegermann_catalog_page_urls_compat(
                self.catalog_url,
                first.html,
            )
        }

        while queued_by_offset and len(self.catalog_page_urls) < self.page_limit:
            offset = min(queued_by_offset)
            page_url = queued_by_offset.pop(offset)
            if offset in visited_offsets:
                continue
            visited_offsets.add(offset)
            try:
                page = self._fetch_page(page_url)
            except Exception as exc:
                self.catalog_page_errors.append(
                    {"url": page_url, "error": str(exc)}
                )
                continue

            self.catalog_page_urls.append(page.requested_url)
            page_items = extract_riegermann_item_urls_compat(
                page.canonical_url,
                page.html,
            )
            new_items = [item for item in page_items if item not in seen_items]
            if not new_items:
                self.catalog_page_errors.append(
                    {
                        "url": page_url,
                        "error": "pagination page produced no new item URLs",
                    }
                )
            else:
                item_urls.extend(new_items)
                seen_items.update(new_items)

            for discovered_url in extract_riegermann_catalog_page_urls_compat(
                page_url,
                page.html,
            ):
                discovered_offset = _catalog_offset(discovered_url)
                if discovered_offset not in visited_offsets:
                    queued_by_offset.setdefault(discovered_offset, discovered_url)

        self.catalog_limit_reached = bool(queued_by_offset)
        self.catalog_coverage_complete = (
            not self.catalog_limit_reached and not self.catalog_page_errors
        )

        anchors = "\n".join(
            f'<a href="{url}">{html.escape(urlparse(url).path.rsplit("/", 1)[-1])}</a>'
            for url in item_urls
        )
        merged_html = (
            first.html
            + "\n<section data-opportunity-engine-catalog-pagination=\"true\">\n"
            + anchors
            + "\n</section>\n"
        )
        encoding = "utf-8"
        return _MergedResponse(
            url=first.final_url,
            content=merged_html.encode(encoding, errors="replace"),
            status_code=first.status_code,
            content_type=first.content_type or "text/html; charset=utf-8",
            encoding=encoding,
        )


def _apply_catalog_coverage(
    live: live_layer.RiegermannLiveResult,
    session: _PaginatedCatalogSession,
) -> None:
    report = live.discovery_result["search_run_report"]
    diagnostics = report["riegermann_live"]
    diagnostics.update(
        {
            "catalog_page_count": len(session.catalog_page_urls),
            "catalog_page_limit": session.page_limit,
            "catalog_page_urls": list(session.catalog_page_urls),
            "catalog_page_errors": list(session.catalog_page_errors),
            "catalog_page_limit_reached": session.catalog_limit_reached,
            "catalog_coverage_complete": session.catalog_coverage_complete,
            "child_lots_observed": diagnostics.get("parsed_child_lot_count", 0),
        }
    )

    parent = next(
        (
            candidate
            for candidate in live.discovery_result["all_discovered_candidates"]
            if candidate.get("page_role") == "AUCTION_EVENT"
        ),
        None,
    )
    if parent is None:
        return

    parent.update(
        {
            "catalog_pages_fetched": len(session.catalog_page_urls),
            "catalog_page_limit": session.page_limit,
            "catalog_coverage_complete": session.catalog_coverage_complete,
            "child_lots_observed": parent.get("child_lot_count", 0),
            "promoted_bulk_lots_observed": parent.get(
                "promoted_bulk_lot_count",
                0,
            ),
        }
    )
    if not session.catalog_coverage_complete:
        missing = list(parent.get("missing_information") or [])
        if "complete public catalog coverage" not in missing:
            missing.insert(0, "complete public catalog coverage")
        parent["missing_information"] = missing
        parent["next_verification_step"] = (
            "Fetch the remaining public catalog pages before verifying bulk lots."
        )
        parent["next_action"] = (
            "Keep the auction outside Top 5 until catalog pagination is complete."
        )
        parent["post_verification_top5_block_reason"] = (
            "catalog_pagination_incomplete"
        )
    elif not parent.get("promoted_bulk_lot_count"):
        parent["next_verification_step"] = (
            "Catalog coverage is complete; no explicit bulk child lot requires "
            "item-page verification."
        )
        parent["next_action"] = (
            "Retain the auction as parent evidence and do not promote ordinary "
            "single garments."
        )


def run_riegermann_live_discovery_compat(
    catalog_url: str,
    *,
    information_url: str | None = None,
    session: Any | None = None,
    timeout: float = 20.0,
    max_response_bytes: int = live_layer.DEFAULT_MAX_RESPONSE_BYTES,
    item_verification_limit: int = 10,
    catalog_page_limit: int = 100,
) -> live_layer.RiegermannLiveResult:
    """Run the live adapter with bounded, deduplicated catalog pagination."""
    if catalog_page_limit < 1 or catalog_page_limit > 200:
        raise ValueError("catalog_page_limit must be between 1 and 200")

    paginated_session = _PaginatedCatalogSession(
        catalog_url,
        upstream=session or live_layer.requests,
        timeout=timeout,
        max_response_bytes=max_response_bytes,
        page_limit=catalog_page_limit,
    )
    live = _ORIGINAL_RUN_RIEGERMANN_LIVE_DISCOVERY(
        catalog_url,
        information_url=information_url,
        session=paginated_session,
        timeout=timeout,
        max_response_bytes=max_response_bytes,
        item_verification_limit=item_verification_limit,
    )
    _apply_catalog_coverage(live, paginated_session)
    return live


def install_riegermann_live_catalog_compatibility() -> None:
    """Install the tested live compatibility functions for the CLI process."""
    live_layer.extract_riegermann_item_urls = extract_riegermann_item_urls_compat
    live_layer.parse_riegermann_catalog_html = parse_riegermann_catalog_html_compat
    live_layer._merge_information_event = _merge_information_event_compat
    live_layer.run_riegermann_live_discovery = run_riegermann_live_discovery_compat
