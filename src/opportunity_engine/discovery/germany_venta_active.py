"""Daily-safe public VENTA auction watch for explicit clothing inventory.

The watch inspects bounded public auction catalogs, completes their public
pagination, and emits at most one parent opportunity per verified clothing
auction. Ordinary garments remain child evidence. Explicit bulk clothing lots
are recorded for later exact item-page verification but are not promoted by this
layer.

No login, bidding, seller contact, purchase, payment, hidden API access,
access-control bypass, currency conversion, tax, customs, logistics, profit or
ROI calculation is performed.
"""
from __future__ import annotations

import hashlib
import html
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests

from opportunity_engine.discovery.clothing_inventory_search import (
    STRONG_LEAD_REQUIRES_VERIFICATION,
)
from opportunity_engine.discovery.germany_venta import (
    ACTIVE,
    ENDED,
    DEFAULT_MAX_RESPONSE_BYTES,
    DEFAULT_USER_AGENT,
    DEFAULT_VENTA_INDEX_URL,
    VentaAuctionIndexEntry,
    VentaCatalogMetadata,
    VentaPublicPage,
    canonicalize_venta_url,
    fetch_venta_auction_index,
    parse_venta_auction_index,
    parse_venta_catalog_metadata,
)

AGGREGATION_MODE = "AUCTION_EVENT_WITH_CHILD_LOTS"
DEFAULT_ACTIVE_CATALOG_LIMIT = 10
DEFAULT_CATALOG_PAGE_LIMIT = 100

_ANCHOR_RE = re.compile(
    r"<a\b[^>]*href\s*=\s*[\"'](?P<href>[^\"']+)[\"'][^>]*>"
    r"(?P<label>.*?)</a>",
    re.I | re.S,
)
_H3_RE = re.compile(r"<h3\b[^>]*>(?P<body>.*?)</h3>", re.I | re.S)
_ITEM_LABEL_RE = re.compile(
    r"^\s*(?P<catalog>[0-9]+)\.(?P<lot>[0-9]+)\s*=>\s*(?P<title>.+?)\s*$",
    re.I,
)
_QUANTITY_RE = re.compile(r"^\s*(?P<quantity>[0-9]+)\s+(?P<title>.+?)\s*$", re.I)
_COMPANY_NAME_CLOTHING_RE = re.compile(
    r"\b(?:apparel|mode|textil|fashion|bekleidung|kleidung)\b",
    re.I,
)
_SCOPE_RE = re.compile(
    r"\b(?:kompletter?|gesamter?|gesamte|warenbestand|lagerbestand|restbestand)\b",
    re.I,
)
_BULK_RE = re.compile(
    r"\b(?:posten|konvolut|warenbestand|lagerbestand|restbestand|sortiment|"
    r"palette(?:n)?|karton(?:s)?|paket(?:e)?|sammlung)\b",
    re.I,
)
_CLOTHING_PATTERNS = (
    ("bekleidung", re.compile(r"bekleidung\w*", re.I)),
    ("kleidung", re.compile(r"(?<!be)kleidung\w*", re.I)),
    ("textilien", re.compile(r"textil\w*", re.I)),
    ("modewaren", re.compile(r"mode(?:waren|bestand|artikel)\w*", re.I)),
    ("konfektion", re.compile(r"konfektion\w*", re.I)),
    ("schuhe", re.compile(r"schuh\w*", re.I)),
    ("jacken", re.compile(r"jacke\w*", re.I)),
    ("maentel", re.compile(r"(?:mantel|mäntel|maentel)\w*", re.I)),
    ("hosen", re.compile(r"hose\w*", re.I)),
    ("kleider", re.compile(r"kleid(?:er|ung)?\w*", re.I)),
    ("hemden", re.compile(r"hemd\w*", re.I)),
    ("pullover", re.compile(r"pullover\w*", re.I)),
    ("lederbekleidung", re.compile(r"leder(?:bekleidung|jacken|hosen|mäntel|maentel)\w*", re.I)),
    ("boutique", re.compile(r"\bboutique\b", re.I)),
)
_GENERIC_HEADINGS = {
    "informationen zur versteigerung",
    "zur beachtung",
    "artikel filtern",
}
_GENERIC_ITEM_LABELS = {
    "",
    "mehr",
    "[mehr...]",
    "details",
}
_ALLOWED_PAGINATION_QUERY_KEYS = {
    "block",
    "order_by_sort",
    "page",
    "search",
    "search_closed",
}


def _strip_html(value: str) -> str:
    fragment = re.sub(
        r"<(script|style|noscript)\b[^>]*>.*?</\1>",
        " ",
        value,
        flags=re.I | re.S,
    )
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return " ".join(html.unescape(fragment).split())


def _matching_clothing_terms(text: str) -> tuple[str, ...]:
    return tuple(label for label, pattern in _CLOTHING_PATTERNS if pattern.search(text))


@dataclass(frozen=True, slots=True)
class VentaCatalogPageIdentity:
    catalog_block_id: str
    page_number: int
    canonical_url: str


@dataclass(frozen=True, slots=True)
class VentaCatalogLot:
    catalog_number: str
    lot_number: str
    object_id: str
    canonical_url: str
    title: str
    quantity: int | None
    listing_status: str
    clothing_evidence: bool
    clothing_terms: tuple[str, ...]
    bulk_evidence: bool
    ordinary_single_garment: bool
    promotion_eligible: bool
    opportunity_identity: str
    parent_opportunity_identity: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class VentaCatalogCrawlResult:
    index_entry: VentaAuctionIndexEntry
    metadata: VentaCatalogMetadata
    page_diagnostics: tuple[dict[str, Any], ...]
    page_errors: tuple[dict[str, Any], ...]
    catalog_page_urls: tuple[str, ...]
    catalog_pages_fetched: int
    catalog_page_limit: int
    catalog_page_limit_reached: bool
    catalog_coverage_complete: bool
    catalog_coverage_reason: str
    catalog_total_results: int | None
    catalog_expected_page_count: int
    catalog_item_url_count: int
    clothing_lots: tuple[VentaCatalogLot, ...]
    ordinary_child_lot_count: int
    observed_bulk_lot_count: int
    explicit_clothing_evidence: bool
    explicit_clothing_terms: tuple[str, ...]
    full_catalog_clothing_scope: bool

    @property
    def opportunity_identity(self) -> str | None:
        return self.metadata.opportunity_identity

    def diagnostics(self) -> dict[str, Any]:
        return {
            "catalog_block_id": self.index_entry.catalog_block_id,
            "catalog_url": self.index_entry.catalog_url,
            "auction_number": self.metadata.auction_number,
            "opportunity_identity": self.opportunity_identity,
            "title": self.metadata.title or self.index_entry.title,
            "listing_status": self.metadata.listing_status,
            "location": self.metadata.location,
            "catalog_pages_fetched": self.catalog_pages_fetched,
            "catalog_page_limit": self.catalog_page_limit,
            "catalog_page_limit_reached": self.catalog_page_limit_reached,
            "catalog_coverage_complete": self.catalog_coverage_complete,
            "catalog_coverage_reason": self.catalog_coverage_reason,
            "catalog_total_results": self.catalog_total_results,
            "catalog_expected_page_count": self.catalog_expected_page_count,
            "catalog_item_url_count": self.catalog_item_url_count,
            "clothing_child_lot_count": len(self.clothing_lots),
            "ordinary_child_lot_count": self.ordinary_child_lot_count,
            "observed_bulk_lot_count": self.observed_bulk_lot_count,
            "promoted_bulk_lot_count": 0,
            "explicit_clothing_evidence": self.explicit_clothing_evidence,
            "explicit_clothing_terms": list(self.explicit_clothing_terms),
            "full_catalog_clothing_scope": self.full_catalog_clothing_scope,
            "catalog_page_urls": list(self.catalog_page_urls),
            "catalog_page_diagnostics": list(self.page_diagnostics),
            "catalog_page_errors": list(self.page_errors),
            "nok_price_fields_written": False,
            "normalized_price_written": False,
        }


@dataclass(frozen=True, slots=True)
class VentaActiveWatchResult:
    discovery_result: dict[str, Any]
    diagnostics: dict[str, Any]


def canonicalize_venta_catalog_page_url(
    url: str,
    *,
    expected_catalog_block_id: str | None = None,
) -> VentaCatalogPageIdentity | None:
    """Accept one exact catalog page while preserving the catalog block scope."""
    direct = canonicalize_venta_url(url)
    if direct is not None and direct.kind == "AUCTION_CATALOG":
        block_id = str(direct.catalog_block_id)
        if expected_catalog_block_id is not None and block_id != str(
            expected_catalog_block_id
        ):
            return None
        return VentaCatalogPageIdentity(
            catalog_block_id=block_id,
            page_number=1,
            canonical_url=direct.canonical_url,
        )

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    if (parsed.hostname or "").casefold().rstrip(".") != "auction.venta24.de":
        return None
    if parsed.path != "/browse.php":
        return None

    query = parse_qs(parsed.query, keep_blank_values=True)
    if not query or set(query) - _ALLOWED_PAGINATION_QUERY_KEYS:
        return None
    block_values = query.get("block") or []
    page_values = query.get("page") or []
    if len(block_values) != 1 or len(page_values) != 1:
        return None
    block_id = block_values[0]
    if not block_id.isdigit():
        return None
    if expected_catalog_block_id is not None and block_id != str(
        expected_catalog_block_id
    ):
        return None
    try:
        page_number = int(page_values[0])
    except ValueError:
        return None
    if page_number < 1:
        return None
    search_values = query.get("search") or ["1"]
    if len(search_values) != 1 or search_values[0] not in {"", "1"}:
        return None
    closed_values = query.get("search_closed") or []
    if len(closed_values) > 1 or (closed_values and closed_values[0] not in {"", "y", "n"}):
        return None

    pairs: list[tuple[str, str]] = []
    for key in sorted(query):
        values = query[key]
        if len(values) != 1:
            return None
        pairs.append((key, values[0]))
    canonical_url = urlunparse(
        (
            "https",
            "auction.venta24.de",
            "/browse.php",
            "",
            urlencode(pairs),
            "",
        )
    )
    return VentaCatalogPageIdentity(
        catalog_block_id=block_id,
        page_number=page_number,
        canonical_url=canonical_url,
    )


def _generated_catalog_page_url(catalog_block_id: str, page_number: int) -> str:
    return urlunparse(
        (
            "https",
            "auction.venta24.de",
            "/browse.php",
            "",
            urlencode(
                (
                    ("block", str(catalog_block_id)),
                    ("order_by_sort", "ends_asc"),
                    ("page", str(page_number)),
                    ("search", "1"),
                    ("search_closed", "y"),
                )
            ),
            "",
        )
    )


def fetch_venta_catalog_page(
    url: str,
    *,
    catalog_block_id: str,
    session: Any | None = None,
    timeout: float = 20.0,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> VentaPublicPage:
    """Fetch one public catalog page and fail closed on scope changes."""
    requested_identity = canonicalize_venta_catalog_page_url(
        url,
        expected_catalog_block_id=catalog_block_id,
    )
    if requested_identity is None:
        raise ValueError("url must be a public VENTA page for the selected catalog")
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if max_response_bytes <= 0:
        raise ValueError("max_response_bytes must be positive")

    client = session or requests
    response = client.get(
        requested_identity.canonical_url,
        timeout=timeout,
        allow_redirects=True,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    response.raise_for_status()
    final_identity = canonicalize_venta_catalog_page_url(
        str(response.url),
        expected_catalog_block_id=catalog_block_id,
    )
    if final_identity is None:
        raise RuntimeError("VENTA catalog redirect left the selected catalog scope")

    content_type = None
    if getattr(response, "headers", None):
        content_type = str(response.headers.get("content-type") or "").strip() or None
    if content_type and "html" not in content_type.casefold():
        raise RuntimeError(f"unexpected VENTA catalog content type: {content_type}")

    raw = bytes(response.content)
    if len(raw) > max_response_bytes:
        raise RuntimeError(f"VENTA catalog page exceeds {max_response_bytes} bytes")
    encoding = getattr(response, "encoding", None) or "utf-8"
    decoded = raw.decode(encoding, errors="replace")
    compact = decoded.casefold()
    if "<html" not in compact and "<!doctype html" not in compact:
        raise RuntimeError("VENTA catalog response is not HTML")
    if any(marker in compact for marker in ("captcha", "cloudflare challenge")):
        raise RuntimeError("VENTA access challenge detected; no bypass attempted")

    return VentaPublicPage(
        requested_url=requested_identity.canonical_url,
        final_url=str(response.url),
        status_code=int(response.status_code),
        content_type=content_type,
        response_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        html=decoded,
    )


def _extract_catalog_heading_evidence(
    source_html: str,
) -> tuple[tuple[str, ...], bool]:
    terms: list[str] = []
    scope = False
    for match in _H3_RE.finditer(source_html):
        body = match.group("body")
        if "<a" in body.casefold():
            continue
        heading = _strip_html(body)
        if heading.casefold() in _GENERIC_HEADINGS:
            continue
        matched = _matching_clothing_terms(heading)
        if not matched:
            continue
        for term in matched:
            if term not in terms:
                terms.append(term)
        if _SCOPE_RE.search(heading):
            scope = True
    return tuple(terms), scope


def parse_venta_catalog_lots(
    catalog_url: str,
    source_html: str,
    *,
    listing_status: str,
    parent_opportunity_identity: str | None,
    full_catalog_clothing_scope: bool = False,
) -> tuple[VentaCatalogLot, ...]:
    """Parse stable item identities and conservative clothing/bulk evidence."""
    grouped: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for anchor in _ANCHOR_RE.finditer(source_html):
        candidate = urljoin(catalog_url, html.unescape(anchor.group("href")).strip())
        identity = canonicalize_venta_url(candidate)
        if (
            identity is None
            or identity.kind != "ITEM_DETAIL"
            or identity.object_id is None
            or identity.catalog_number is None
            or identity.lot_number is None
        ):
            continue
        object_id = identity.object_id
        if object_id not in grouped:
            grouped[object_id] = {"identity": identity, "labels": []}
            order.append(object_id)
        label = _strip_html(anchor.group("label")).strip()
        if label and label.casefold() not in _GENERIC_ITEM_LABELS:
            grouped[object_id]["labels"].append(label)

    lots: list[VentaCatalogLot] = []
    for object_id in order:
        row = grouped[object_id]
        identity = row["identity"]
        labels = row["labels"]
        label = max(labels, key=len) if labels else f"VENTA object {object_id}"
        match = _ITEM_LABEL_RE.match(label)
        raw_title = match.group("title") if match else label
        quantity_match = _QUANTITY_RE.match(raw_title)
        quantity = int(quantity_match.group("quantity")) if quantity_match else None
        title = quantity_match.group("title") if quantity_match else raw_title
        title = " ".join(title.split())
        clothing_terms = _matching_clothing_terms(title)
        clothing_evidence = bool(clothing_terms) or full_catalog_clothing_scope
        bulk_evidence = bool(_BULK_RE.search(title)) or (
            quantity is not None and quantity > 1
        )
        ordinary = clothing_evidence and not bulk_evidence
        lots.append(
            VentaCatalogLot(
                catalog_number=str(identity.catalog_number),
                lot_number=str(identity.lot_number),
                object_id=str(identity.object_id),
                canonical_url=identity.canonical_url,
                title=title,
                quantity=quantity,
                listing_status=listing_status,
                clothing_evidence=clothing_evidence,
                clothing_terms=clothing_terms,
                bulk_evidence=bulk_evidence,
                ordinary_single_garment=ordinary,
                promotion_eligible=False,
                opportunity_identity=f"venta-object:{identity.object_id}",
                parent_opportunity_identity=parent_opportunity_identity,
            )
        )
    return tuple(lots)


def _extract_catalog_page_urls(
    catalog_url: str,
    source_html: str,
    *,
    catalog_block_id: str,
    expected_page_count: int,
) -> dict[int, str]:
    pages: dict[int, str] = {1: canonicalize_venta_url(catalog_url).canonical_url}  # type: ignore[union-attr]
    for anchor in _ANCHOR_RE.finditer(source_html):
        candidate = urljoin(catalog_url, html.unescape(anchor.group("href")).strip())
        page_identity = canonicalize_venta_catalog_page_url(
            candidate,
            expected_catalog_block_id=catalog_block_id,
        )
        if page_identity is None:
            continue
        if 1 <= page_identity.page_number <= expected_page_count:
            pages.setdefault(page_identity.page_number, page_identity.canonical_url)
    for page_number in range(2, expected_page_count + 1):
        pages.setdefault(
            page_number,
            _generated_catalog_page_url(catalog_block_id, page_number),
        )
    return pages


def crawl_venta_catalog(
    entry: VentaAuctionIndexEntry,
    *,
    session: Any | None = None,
    timeout: float = 20.0,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    catalog_page_limit: int = DEFAULT_CATALOG_PAGE_LIMIT,
) -> VentaCatalogCrawlResult:
    """Crawl one active catalog with bounded, identity-preserving pagination."""
    if catalog_page_limit < 1 or catalog_page_limit > 200:
        raise ValueError("catalog_page_limit must be between 1 and 200")
    if entry.listing_status != ACTIVE:
        raise ValueError("only active VENTA catalog entries may be crawled")

    first_page = fetch_venta_catalog_page(
        entry.catalog_url,
        catalog_block_id=entry.catalog_block_id,
        session=session,
        timeout=timeout,
        max_response_bytes=max_response_bytes,
    )
    first_metadata = parse_venta_catalog_metadata(entry.catalog_url, first_page.html)
    expected_page_count = max(1, int(first_metadata.page_count or 1))
    page_limit_reached = expected_page_count > catalog_page_limit
    target_page_count = min(expected_page_count, catalog_page_limit)
    page_urls = _extract_catalog_page_urls(
        entry.catalog_url,
        first_page.html,
        catalog_block_id=entry.catalog_block_id,
        expected_page_count=target_page_count,
    )
    heading_terms, full_scope = _extract_catalog_heading_evidence(first_page.html)

    page_diagnostics: list[dict[str, Any]] = [first_page.diagnostics()]
    page_errors: list[dict[str, Any]] = []
    item_urls: dict[str, str] = {}
    lots_by_object: dict[str, VentaCatalogLot] = {}
    observed_auction_number = first_metadata.auction_number

    def absorb(page: VentaPublicPage) -> None:
        nonlocal observed_auction_number
        metadata = parse_venta_catalog_metadata(entry.catalog_url, page.html)
        if (
            observed_auction_number is not None
            and metadata.auction_number is not None
            and metadata.auction_number != observed_auction_number
        ):
            raise RuntimeError("VENTA pagination crossed into another auction number")
        if observed_auction_number is None:
            observed_auction_number = metadata.auction_number
        parent_identity = (
            f"venta-auction:{observed_auction_number}"
            if observed_auction_number is not None
            else None
        )
        for item_url, object_id in zip(
            metadata.item_urls,
            metadata.item_object_ids,
            strict=True,
        ):
            item_urls.setdefault(object_id, item_url)
        for lot in parse_venta_catalog_lots(
            entry.catalog_url,
            page.html,
            listing_status=metadata.listing_status,
            parent_opportunity_identity=parent_identity,
            full_catalog_clothing_scope=full_scope,
        ):
            lots_by_object.setdefault(lot.object_id, lot)

    absorb(first_page)
    for page_number in range(2, target_page_count + 1):
        page_url = page_urls[page_number]
        try:
            page = fetch_venta_catalog_page(
                page_url,
                catalog_block_id=entry.catalog_block_id,
                session=session,
                timeout=timeout,
                max_response_bytes=max_response_bytes,
            )
            absorb(page)
            page_diagnostics.append(page.diagnostics())
        except Exception as exc:
            page_errors.append(
                {
                    "page_number": page_number,
                    "url": page_url,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    metadata = VentaCatalogMetadata(
        catalog_block_id=first_metadata.catalog_block_id,
        auction_number=observed_auction_number,
        title=first_metadata.title,
        listing_status=first_metadata.listing_status,
        location=first_metadata.location,
        total_results=first_metadata.total_results,
        page_count=first_metadata.page_count,
        item_urls=tuple(item_urls.values()),
        item_object_ids=tuple(item_urls.keys()),
        clothing_evidence=first_metadata.clothing_evidence,
        clothing_terms=first_metadata.clothing_terms,
    )
    clothing_lots = tuple(
        lot for lot in lots_by_object.values() if lot.clothing_evidence
    )
    explicit_terms: list[str] = []
    for term in (*entry.clothing_terms, *heading_terms):
        if term not in explicit_terms:
            explicit_terms.append(term)
    for lot in clothing_lots:
        for term in lot.clothing_terms:
            if term not in explicit_terms:
                explicit_terms.append(term)
    explicit_clothing = bool(entry.clothing_evidence or heading_terms or clothing_lots)

    contiguous_pages_complete = (
        not page_limit_reached
        and not page_errors
        and len(page_diagnostics) == expected_page_count
    )
    result_count_complete = (
        metadata.total_results is None
        or len(item_urls) == metadata.total_results
    )
    coverage_complete = contiguous_pages_complete and result_count_complete
    if page_limit_reached:
        coverage_reason = "catalog_page_limit_reached"
    elif page_errors:
        coverage_reason = "catalog_page_fetch_errors"
    elif not result_count_complete:
        coverage_reason = "catalog_item_count_mismatch"
    elif coverage_complete:
        coverage_reason = "complete"
    else:
        coverage_reason = "catalog_coverage_unproven"

    return VentaCatalogCrawlResult(
        index_entry=entry,
        metadata=metadata,
        page_diagnostics=tuple(page_diagnostics),
        page_errors=tuple(page_errors),
        catalog_page_urls=tuple(page_urls[number] for number in sorted(page_urls)),
        catalog_pages_fetched=len(page_diagnostics),
        catalog_page_limit=catalog_page_limit,
        catalog_page_limit_reached=page_limit_reached,
        catalog_coverage_complete=coverage_complete,
        catalog_coverage_reason=coverage_reason,
        catalog_total_results=metadata.total_results,
        catalog_expected_page_count=expected_page_count,
        catalog_item_url_count=len(item_urls),
        clothing_lots=clothing_lots,
        ordinary_child_lot_count=sum(
            lot.ordinary_single_garment for lot in clothing_lots
        ),
        observed_bulk_lot_count=sum(lot.bulk_evidence for lot in clothing_lots),
        explicit_clothing_evidence=explicit_clothing,
        explicit_clothing_terms=tuple(explicit_terms),
        full_catalog_clothing_scope=full_scope,
    )


def _candidate_from_catalog(crawl: VentaCatalogCrawlResult) -> dict[str, Any]:
    metadata = crawl.metadata
    identity = crawl.opportunity_identity
    title = metadata.title or crawl.index_entry.title
    bulk_urls = [
        lot.canonical_url for lot in crawl.clothing_lots if lot.bulk_evidence
    ]
    if bulk_urls:
        next_step = (
            "Verify observed bulk clothing lots on exact public item pages before "
            "any item-level promotion."
        )
        next_action = "Retain the auction parent and verify explicit bulk child lots."
    else:
        next_step = (
            "Keep watching the active catalog; no explicit bulk clothing lot is "
            "currently eligible for exact item-page verification."
        )
        next_action = "Retain the auction as parent evidence only."
    confirmed = [
        "source: VENTA Industrieversteigerungen",
        f"catalog block: {crawl.index_entry.catalog_block_id}",
        f"auction identity: {identity}",
        f"catalog pages fetched: {crawl.catalog_pages_fetched}",
        f"catalog items observed: {crawl.catalog_item_url_count}",
        f"clothing child lots observed: {len(crawl.clothing_lots)}",
        f"explicit bulk clothing lots observed: {crawl.observed_bulk_lot_count}",
    ]
    if metadata.location:
        confirmed.append(f"location: {metadata.location}")
    missing = [
        "exact item-page verification for observed bulk clothing lots",
        "cross-border logistics basis",
        "documented final payable price",
    ]
    return {
        "title": title,
        "scenario": "AUCTION",
        "opportunity_state": STRONG_LEAD_REQUIRES_VERIFICATION,
        "reason": (
            "verified VENTA clothing auction event retained as one parent "
            "opportunity with child lots"
        ),
        "page_role": "AUCTION_EVENT",
        "opportunity_identity": identity,
        "identity_stable": identity is not None,
        "top5_eligible": False,
        "analysis_eligible": False,
        "listing_status": metadata.listing_status,
        "market_code": "DE",
        "currency": "EUR",
        "location": metadata.location,
        "company_name": None,
        "inventory_type": "clothing_auction_event",
        "price": None,
        "price_nok": None,
        "bid_price_nok": None,
        "quantity": None,
        "source_urls": [crawl.index_entry.catalog_url],
        "source_providers": ["VENTA Industrieversteigerungen"],
        "aggregation_mode": AGGREGATION_MODE,
        "child_lot_count": len(crawl.clothing_lots),
        "ordinary_child_lot_count": crawl.ordinary_child_lot_count,
        "promoted_bulk_lot_count": 0,
        "observed_bulk_lot_count": crawl.observed_bulk_lot_count,
        "bulk_item_urls_requiring_verification": bulk_urls,
        "child_lots": [lot.to_dict() for lot in crawl.clothing_lots],
        "confirmed_information": confirmed,
        "missing_information": missing,
        "next_verification_step": next_step,
        "next_action": next_action,
        "verification": [
            {
                "url": crawl.index_entry.catalog_url,
                "title": title,
                "text": None,
                "location": metadata.location,
                "inventory_type": "clothing_auction_event",
                "price_nok": None,
                "bid_price_nok": None,
                "quantity": None,
                "published_at": None,
                "listing_status": metadata.listing_status,
                "page_role": "AUCTION_EVENT",
                "opportunity_identity": identity,
                "identity_stable": identity is not None,
                "clothing_inventory_evidence": True,
                "sale_evidence": True,
                "event_scenario": "AUCTION",
                "bounded_context": (
                    f"{title} | pages: {crawl.catalog_pages_fetched} | "
                    f"items: {crawl.catalog_item_url_count} | clothing lots: "
                    f"{len(crawl.clothing_lots)} | bulk lots observed: "
                    f"{crawl.observed_bulk_lot_count}"
                ),
                "verified": crawl.catalog_coverage_complete,
                "error": None,
            }
        ],
        "verification_content_match": crawl.catalog_coverage_complete,
        "source_runtime_status": "PLANNED",
        "catalog_pages_fetched": crawl.catalog_pages_fetched,
        "catalog_page_limit": crawl.catalog_page_limit,
        "catalog_coverage_complete": crawl.catalog_coverage_complete,
        "catalog_coverage_reason": crawl.catalog_coverage_reason,
        "catalog_total_results": crawl.catalog_total_results,
        "catalog_item_url_count": crawl.catalog_item_url_count,
        "post_verification_top5_block_reason": "specific_item_listing_not_verified",
    }


def run_venta_active_clothing_watch(
    index_url: str = DEFAULT_VENTA_INDEX_URL,
    *,
    session: Any | None = None,
    timeout: float = 20.0,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    catalog_limit: int = DEFAULT_ACTIVE_CATALOG_LIMIT,
    catalog_page_limit: int = DEFAULT_CATALOG_PAGE_LIMIT,
) -> VentaActiveWatchResult:
    """Inspect active VENTA catalogs and emit only exact clothing-event leads."""
    if catalog_limit < 1 or catalog_limit > 25:
        raise ValueError("catalog_limit must be between 1 and 25")
    if catalog_page_limit < 1 or catalog_page_limit > 200:
        raise ValueError("catalog_page_limit must be between 1 and 200")

    index_page = fetch_venta_auction_index(
        index_url,
        session=session,
        timeout=timeout,
        max_response_bytes=max_response_bytes,
    )
    entries = parse_venta_auction_index(index_page.final_url, index_page.html)
    active_entries = [entry for entry in entries if entry.listing_status == ACTIVE]
    selected_entries = active_entries[:catalog_limit]

    catalog_runs: list[VentaCatalogCrawlResult] = []
    catalog_errors: list[dict[str, Any]] = []
    for entry in selected_entries:
        try:
            crawl = crawl_venta_catalog(
                entry,
                session=session,
                timeout=timeout,
                max_response_bytes=max_response_bytes,
                catalog_page_limit=catalog_page_limit,
            )
            if not crawl.catalog_coverage_complete:
                raise RuntimeError(
                    "VENTA catalog coverage incomplete: "
                    f"{crawl.catalog_coverage_reason}"
                )
            catalog_runs.append(crawl)
        except Exception as exc:
            catalog_errors.append(
                {
                    "catalog_block_id": entry.catalog_block_id,
                    "url": entry.catalog_url,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    clothing_runs = [run for run in catalog_runs if run.explicit_clothing_evidence]
    candidates = [_candidate_from_catalog(run) for run in clothing_runs]
    company_name_only_false_positives = [
        entry
        for entry in entries
        if _COMPANY_NAME_CLOTHING_RE.search(entry.title)
        and not entry.clothing_evidence
    ]
    total_catalog_items = sum(run.catalog_item_url_count for run in catalog_runs)
    total_clothing_lots = sum(len(run.clothing_lots) for run in clothing_runs)
    total_observed_bulk_lots = sum(
        run.observed_bulk_lot_count for run in clothing_runs
    )
    diagnostics = {
        "index_page": index_page.diagnostics(),
        "auction_entries_discovered": len(entries),
        "active_catalog_entries_discovered": len(active_entries),
        "selected_catalog_count": len(selected_entries),
        "successful_catalog_count": len(catalog_runs),
        "failed_catalog_count": len(catalog_errors),
        "catalog_limit": catalog_limit,
        "catalog_limit_reached": len(active_entries) > catalog_limit,
        "clothing_catalog_count": len(clothing_runs),
        "catalog_item_url_count": total_catalog_items,
        "clothing_child_lot_count": total_clothing_lots,
        "ordinary_child_lot_count": sum(
            run.ordinary_child_lot_count for run in clothing_runs
        ),
        "observed_bulk_lot_count": total_observed_bulk_lots,
        "promoted_bulk_lot_count": 0,
        "single_garment_candidate_count": 0,
        "company_name_only_false_positive_count": len(
            company_name_only_false_positives
        ),
        "index_entries": [entry.to_dict() for entry in entries],
        "selected_catalogs": [entry.to_dict() for entry in selected_entries],
        "catalog_runs": [run.diagnostics() for run in catalog_runs],
        "catalog_errors": catalog_errors,
        "nok_price_fields_written": False,
        "normalized_price_written": False,
        "zero_clothing_results_are_valid": True,
    }
    status = "PASS" if not catalog_errors else "PARTIAL"
    report = {
        "schema_version": "clothing-inventory-discovery-search-1.3",
        "domain": "CLOTHING_INVENTORY",
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "provider": "VENTA active public catalog watch",
        "queries_submitted": 0,
        "query_matrix": [],
        "hits_received": len(entries) + total_catalog_items,
        "unique_public_urls": len(entries) + total_catalog_items,
        "merged_candidates": len(candidates),
        "duplicates_merged": 0,
        "rejected_results": len(entries) - len(clothing_runs),
        "confirmed_sales": 0,
        "strong_leads_requiring_verification": len(candidates),
        "ended_or_historical": sum(
            entry.listing_status == ENDED for entry in entries
        ),
        "sources_discovered": 1,
        "discovery_bands": {"HIGH": 0, "REVIEW": len(candidates), "LOW": 0},
        "verification_attempted": bool(selected_entries),
        "verification_limit": catalog_limit,
        "top5_count": 0,
        "top5_eligible_count": 0,
        "generic_pages_excluded": len(entries) - len(clothing_runs),
        "verification_failures": len(catalog_errors),
        "false_positive_guard_triggered": len(
            company_name_only_false_positives
        ),
        "errors": catalog_errors,
        "execution_status": status,
        "opportunity_quality_status": (
            "LEADS_REQUIRING_VERIFICATION"
            if candidates
            else "NO_VALID_OPPORTUNITIES"
        ),
        "status": status,
        "no_opportunities_found": not candidates,
        "automatic_contact": False,
        "automatic_purchase_decision": False,
        "financial_ranking_used": False,
        "source_mode": "VENTA_ACTIVE_WATCH",
        "source_target": "VENTA_ACTIVE_AUCTIONS",
        "query_pack": "VENTA_ACTIVE_INDEX_V1",
        "market_code": "DE",
        "currency": "EUR",
        "currency_conversion_performed": False,
        "tax_calculation_performed": False,
        "customs_calculation_performed": False,
        "logistics_calculation_performed": False,
        "source_adapter": {
            "source": "VENTA Industrieversteigerungen",
            "market_code": "DE",
            "currency": "EUR",
            "aggregation_mode": AGGREGATION_MODE,
            "parent_candidate_count": len(candidates),
            "child_lot_count": total_clothing_lots,
            "observed_bulk_lot_count": total_observed_bulk_lots,
            "promoted_bulk_candidate_count": 0,
            "single_garment_candidate_count": 0,
            "nok_price_fields_written": False,
            "normalized_price_written": False,
        },
        "venta_active": diagnostics,
    }
    discovery = {
        "all_discovered_candidates": candidates,
        "discovery_top5": [],
        "source_adapter": report["source_adapter"],
        "search_run_report": report,
    }
    return VentaActiveWatchResult(
        discovery_result=discovery,
        diagnostics=diagnostics,
    )
