"""Daily-safe public Deutsche Pfandverwertung clothing-auction watch.

The watch reads only the public auction overview, public catalog pages and exact
public item pages. It preserves one parent opportunity per verified clothing
auction, keeps ordinary garments as child evidence, and verifies explicit bulk
lots on their exact item pages. The source remains PLANNED until a current live
clothing catalog and the complete persistence path are validated on main.

No login, registration, bidding, seller contact, purchase, payment, hidden API
access, access-control bypass, FX conversion, tax, customs, logistics, profit or
ROI calculation is performed.
"""
from __future__ import annotations

import hashlib
import html
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests

from opportunity_engine.discovery.clothing_inventory_search import (
    STRONG_LEAD_REQUIRES_VERIFICATION,
)
from opportunity_engine.discovery.germany_deutsche_pfandverwertung import (
    ACTIVE,
    ENDED,
    UNKNOWN,
    DEFAULT_DPV_INDEX_URL,
    DEFAULT_MAX_RESPONSE_BYTES,
    DEFAULT_USER_AGENT,
    DpvAuctionIndexEntry,
    DpvPublicPage,
    canonicalize_dpv_url,
    fetch_dpv_auction_index,
    parse_dpv_auction_index,
    parse_dpv_item_metadata,
)

AGGREGATION_MODE = "AUCTION_EVENT_WITH_CHILD_LOTS"
DEFAULT_ACTIVE_CATALOG_LIMIT = 10
DEFAULT_CATALOG_PAGE_LIMIT = 100
DEFAULT_ITEM_VERIFICATION_LIMIT = 10

_ANCHOR_RE = re.compile(
    r"<a\b[^>]*href\s*=\s*[\"'](?P<href>[^\"']+)[\"'][^>]*>"
    r"(?P<label>.*?)</a>",
    re.I | re.S,
)
_H1_RE = re.compile(r"<h1\b[^>]*>(?P<body>.*?)</h1>", re.I | re.S)
_HEADING_RE = re.compile(r"<h[1-4]\b[^>]*>(?P<body>.*?)</h[1-4]>", re.I | re.S)
_PAGE_COUNT_RE = re.compile(
    r"(?:Seite|Page)\s*(?P<page>[0-9]+)\s*(?:von|of)\s*(?P<count>[0-9]+)",
    re.I,
)
_ITEM_COUNT_RE = re.compile(
    r"(?:Anzahl\s+Artikel|Quantity\s+items|Objekte\s+gesamt)\s*:?\s*(?P<count>[0-9]+)",
    re.I,
)
_LOCATION_RE = re.compile(
    r"(?:Standort|Location)\s*:?\s*(?P<location>.+?)"
    r"(?=\s+(?:Versteigerung|Auktion|Los|Artikel|Gebot|$))",
    re.I,
)
_QUANTITY_RE = re.compile(
    r"\b(?P<number>[0-9][0-9. ]*)\s*"
    r"(?P<unit>Paar|St(?:ü|ue)ck|Paletten|Packungen|Sets?|Artikel|Kartons?|Pakete?)\b",
    re.I,
)
_SCOPE_RE = re.compile(
    r"\b(?:kompletter?|gesamter?|gesamte|warenbestand|lagerbestand|restbestand|"
    r"inventar|sortiment|geschäftsauflösung|geschaeftsaufloesung)\b",
    re.I,
)
_BULK_RE = re.compile(
    r"\b(?:konvolut|gro(?:ß|ss)konvolut|sachgesamtheit|posten|warenbestand|"
    r"lagerbestand|restbestand|sortiment|paletten?|kartons?|pakete?)\b",
    re.I,
)
_CLOTHING_PATTERNS = (
    ("bekleidung", re.compile(r"bekleidung\w*", re.I)),
    ("kleidung", re.compile(r"(?<!be)kleidung\w*", re.I)),
    ("textilien", re.compile(r"textil\w*", re.I)),
    ("schuhe", re.compile(r"schuh\w*", re.I)),
    ("unterwaesche", re.compile(r"unterw(?:ä|ae)sche\w*", re.I)),
    ("jacken", re.compile(r"jacke\w*", re.I)),
    ("hosen", re.compile(r"hose\w*", re.I)),
    ("maentel", re.compile(r"(?:mantel|mäntel|maentel)\w*", re.I)),
    ("schals", re.compile(r"schal\w*", re.I)),
    ("taschen", re.compile(r"tasche\w*", re.I)),
    ("socken", re.compile(r"socke\w*", re.I)),
    ("handschuhe", re.compile(r"handschuh\w*", re.I)),
    ("modewaren", re.compile(r"mode(?:waren|artikel|bestand)\w*", re.I)),
)
_GENERIC_LABELS = {"", "mehr", "details", "ansehen", "view", "katalog ansehen"}
_ALLOWED_PAGE_QUERY_KEYS = {
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


def _unique(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class DpvCatalogPageIdentity:
    catalog_block_id: str
    page_number: int
    canonical_url: str


@dataclass(frozen=True, slots=True)
class DpvCatalogLot:
    object_id: str
    canonical_url: str
    title: str
    listing_status: str
    clothing_evidence: bool
    clothing_terms: tuple[str, ...]
    bulk_evidence: bool
    bulk_terms: tuple[str, ...]
    quantity_mentions: tuple[str, ...]
    ordinary_single_garment: bool
    exact_item_verified: bool
    exact_item_verification_error: str | None
    source_displayed_amount_eur: float | None
    source_displayed_amount_kind: str | None
    source_bid_count: int | None
    location: str | None
    promotion_eligible: bool
    opportunity_identity: str
    parent_opportunity_identity: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DpvCatalogCrawlResult:
    index_entry: DpvAuctionIndexEntry
    title: str
    location: str | None
    listing_status: str
    page_diagnostics: tuple[dict[str, Any], ...]
    page_errors: tuple[dict[str, Any], ...]
    item_verification_errors: tuple[dict[str, Any], ...]
    catalog_page_urls: tuple[str, ...]
    catalog_pages_fetched: int
    catalog_page_limit: int
    catalog_page_limit_reached: bool
    catalog_coverage_complete: bool
    catalog_coverage_reason: str
    catalog_total_results: int | None
    catalog_expected_page_count: int
    catalog_item_url_count: int
    clothing_lots: tuple[DpvCatalogLot, ...]
    ordinary_child_lot_count: int
    observed_bulk_lot_count: int
    verified_bulk_lot_count: int
    explicit_clothing_evidence: bool
    explicit_clothing_terms: tuple[str, ...]
    full_catalog_clothing_scope: bool

    @property
    def opportunity_identity(self) -> str:
        return self.index_entry.opportunity_identity

    def diagnostics(self) -> dict[str, Any]:
        return {
            "catalog_block_id": self.index_entry.catalog_block_id,
            "catalog_url": self.index_entry.catalog_url,
            "opportunity_identity": self.opportunity_identity,
            "title": self.title,
            "listing_status": self.listing_status,
            "location": self.location,
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
            "verified_bulk_lot_count": self.verified_bulk_lot_count,
            "promoted_bulk_lot_count": 0,
            "explicit_clothing_evidence": self.explicit_clothing_evidence,
            "explicit_clothing_terms": list(self.explicit_clothing_terms),
            "full_catalog_clothing_scope": self.full_catalog_clothing_scope,
            "catalog_page_urls": list(self.catalog_page_urls),
            "catalog_page_diagnostics": list(self.page_diagnostics),
            "catalog_page_errors": list(self.page_errors),
            "item_verification_errors": list(self.item_verification_errors),
            "nok_price_fields_written": False,
            "normalized_price_written": False,
        }


@dataclass(frozen=True, slots=True)
class DpvActiveWatchResult:
    discovery_result: dict[str, Any]
    diagnostics: dict[str, Any]


def canonicalize_dpv_catalog_page_url(
    url: str,
    *,
    expected_catalog_block_id: str | None = None,
) -> DpvCatalogPageIdentity | None:
    """Accept one exact public catalog page without leaving its catalog block."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    host = (parsed.hostname or "").casefold().rstrip(".")
    if host == "versteigerungen-deutsche-pfandverwertung.de":
        host = "www.versteigerungen-deutsche-pfandverwertung.de"
    if host != "www.versteigerungen-deutsche-pfandverwertung.de":
        return None

    direct = canonicalize_dpv_url(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if direct is not None and direct.kind == "AUCTION_CATALOG":
        block_id = str(direct.catalog_block_id)
        if expected_catalog_block_id is not None and block_id != str(expected_catalog_block_id):
            return None
        if set(query) - _ALLOWED_PAGE_QUERY_KEYS:
            return None
        page_values = query.get("page") or ["1"]
        if len(page_values) != 1:
            return None
        try:
            page_number = int(page_values[0] or "1")
        except ValueError:
            return None
        if page_number < 1:
            return None
        if not query or page_number == 1:
            canonical_url = direct.canonical_url
        else:
            pairs: list[tuple[str, str]] = []
            for key in sorted(query):
                values = query[key]
                if len(values) != 1:
                    return None
                pairs.append((key, values[0]))
            canonical_url = urlunparse(
                ("https", host, parsed.path, "", urlencode(pairs), "")
            )
        return DpvCatalogPageIdentity(block_id, page_number, canonical_url)

    if parsed.path != "/browse.php" or not query or set(query) - _ALLOWED_PAGE_QUERY_KEYS:
        return None
    block_values = query.get("block") or []
    page_values = query.get("page") or []
    if len(block_values) != 1 or len(page_values) != 1:
        return None
    block_id = block_values[0]
    if not block_id.isdigit():
        return None
    if expected_catalog_block_id is not None and block_id != str(expected_catalog_block_id):
        return None
    try:
        page_number = int(page_values[0])
    except ValueError:
        return None
    if page_number < 1:
        return None
    pairs = []
    for key in sorted(query):
        values = query[key]
        if len(values) != 1:
            return None
        pairs.append((key, values[0]))
    return DpvCatalogPageIdentity(
        block_id,
        page_number,
        urlunparse(("https", host, "/browse.php", "", urlencode(pairs), "")),
    )


def _generated_catalog_page_url(catalog_block_id: str, page_number: int) -> str:
    return urlunparse(
        (
            "https",
            "www.versteigerungen-deutsche-pfandverwertung.de",
            "/browse.php",
            "",
            urlencode(
                (
                    ("block", str(catalog_block_id)),
                    ("order_by_sort", "ends_asc"),
                    ("page", str(page_number)),
                    ("search", "1"),
                    ("search_closed", "n"),
                )
            ),
            "",
        )
    )


def _validate_html_response(
    response: Any,
    *,
    max_response_bytes: int,
    label: str,
) -> tuple[str | None, bytes, str]:
    content_type = None
    if getattr(response, "headers", None):
        content_type = str(response.headers.get("content-type") or "").strip() or None
    if content_type and "html" not in content_type.casefold():
        raise RuntimeError(f"unexpected {label} content type: {content_type}")
    raw = bytes(response.content)
    if len(raw) > max_response_bytes:
        raise RuntimeError(f"{label} exceeds {max_response_bytes} bytes")
    encoding = getattr(response, "encoding", None) or "utf-8"
    decoded = raw.decode(encoding, errors="replace")
    compact = decoded.casefold()
    if "<html" not in compact and "<!doctype html" not in compact:
        raise RuntimeError(f"{label} response is not HTML")
    if any(
        marker in compact
        for marker in ("captcha", "cloudflare challenge", "access denied")
    ):
        raise RuntimeError(f"{label} access challenge detected; no bypass attempted")
    return content_type, raw, decoded


def fetch_dpv_catalog_page(
    url: str,
    *,
    catalog_block_id: str,
    session: Any | None = None,
    timeout: float = 20.0,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> DpvPublicPage:
    identity = canonicalize_dpv_catalog_page_url(
        url,
        expected_catalog_block_id=catalog_block_id,
    )
    if identity is None:
        raise ValueError("url must be a public DPV page for the selected catalog")
    if timeout <= 0 or max_response_bytes <= 0:
        raise ValueError("timeout and max_response_bytes must be positive")
    client = session or requests
    response = client.get(
        identity.canonical_url,
        timeout=timeout,
        allow_redirects=True,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    response.raise_for_status()
    final_identity = canonicalize_dpv_catalog_page_url(
        str(response.url),
        expected_catalog_block_id=catalog_block_id,
    )
    if final_identity is None:
        raise RuntimeError("DPV catalog redirect left the selected catalog scope")
    content_type, raw, decoded = _validate_html_response(
        response,
        max_response_bytes=max_response_bytes,
        label="Deutsche Pfandverwertung catalog",
    )
    return DpvPublicPage(
        requested_url=identity.canonical_url,
        final_url=str(response.url),
        status_code=int(response.status_code),
        content_type=content_type,
        response_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        html=decoded,
    )


def fetch_dpv_item_page(
    url: str,
    *,
    object_id: str,
    session: Any | None = None,
    timeout: float = 20.0,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> DpvPublicPage:
    identity = canonicalize_dpv_url(url)
    if identity is None or identity.kind != "ITEM_DETAIL" or identity.object_id != str(object_id):
        raise ValueError("url must be the exact public DPV item page")
    client = session or requests
    response = client.get(
        identity.canonical_url,
        timeout=timeout,
        allow_redirects=True,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    response.raise_for_status()
    final_identity = canonicalize_dpv_url(str(response.url))
    if final_identity is None or final_identity.kind != "ITEM_DETAIL" or final_identity.object_id != str(object_id):
        raise RuntimeError("DPV item redirect changed the exact object identity")
    content_type, raw, decoded = _validate_html_response(
        response,
        max_response_bytes=max_response_bytes,
        label="Deutsche Pfandverwertung item",
    )
    return DpvPublicPage(
        requested_url=identity.canonical_url,
        final_url=str(response.url),
        status_code=int(response.status_code),
        content_type=content_type,
        response_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        html=decoded,
    )


def _catalog_metadata(
    entry: DpvAuctionIndexEntry,
    source_html: str,
) -> tuple[str, str | None, int, int | None, tuple[str, ...], bool]:
    visible = _strip_html(source_html)
    title_match = _H1_RE.search(source_html)
    title = _strip_html(title_match.group("body")) if title_match else entry.title
    location_match = _LOCATION_RE.search(visible)
    location = (
        " ".join(location_match.group("location").split())
        if location_match
        else None
    )
    page_matches = list(_PAGE_COUNT_RE.finditer(visible))
    page_count = max((int(match.group("count")) for match in page_matches), default=1)
    item_match = _ITEM_COUNT_RE.search(visible)
    total_results = int(item_match.group("count")) if item_match else entry.item_count
    heading_text = " ".join(
        _strip_html(match.group("body")) for match in _HEADING_RE.finditer(source_html)
    )
    evidence_text = " | ".join(filter(None, (entry.title, entry.summary, heading_text)))
    clothing_terms = _matching_clothing_terms(evidence_text)
    full_scope = bool(clothing_terms and _SCOPE_RE.search(evidence_text))
    return title, location, page_count, total_results, clothing_terms, full_scope


def _extract_catalog_page_urls(
    catalog_url: str,
    source_html: str,
    *,
    catalog_block_id: str,
    expected_page_count: int,
) -> dict[int, str]:
    direct = canonicalize_dpv_url(catalog_url)
    if direct is None:
        raise ValueError("catalog_url lost its DPV identity")
    pages: dict[int, str] = {1: direct.canonical_url}
    for anchor in _ANCHOR_RE.finditer(source_html):
        candidate = urljoin(catalog_url, html.unescape(anchor.group("href")).strip())
        identity = canonicalize_dpv_catalog_page_url(
            candidate,
            expected_catalog_block_id=catalog_block_id,
        )
        if identity is not None and 1 <= identity.page_number <= expected_page_count:
            pages.setdefault(identity.page_number, identity.canonical_url)
    for page_number in range(2, expected_page_count + 1):
        pages.setdefault(
            page_number,
            _generated_catalog_page_url(catalog_block_id, page_number),
        )
    return pages


def parse_dpv_catalog_lots(
    catalog_url: str,
    source_html: str,
    *,
    listing_status: str,
    parent_opportunity_identity: str,
    full_catalog_clothing_scope: bool,
) -> tuple[DpvCatalogLot, ...]:
    grouped: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for anchor in _ANCHOR_RE.finditer(source_html):
        candidate = urljoin(catalog_url, html.unescape(anchor.group("href")).strip())
        identity = canonicalize_dpv_url(candidate)
        if identity is None or identity.kind != "ITEM_DETAIL" or identity.object_id is None:
            continue
        object_id = str(identity.object_id)
        if object_id not in grouped:
            grouped[object_id] = {"identity": identity, "labels": []}
            order.append(object_id)
        label = _strip_html(anchor.group("label")).strip()
        if label.casefold() not in _GENERIC_LABELS:
            grouped[object_id]["labels"].append(label)

    lots: list[DpvCatalogLot] = []
    for object_id in order:
        group = grouped[object_id]
        labels = group["labels"]
        title = max(labels, key=len) if labels else f"DPV lot {object_id}"
        clothing_terms = _matching_clothing_terms(title)
        clothing_evidence = bool(clothing_terms or full_catalog_clothing_scope)
        quantity_mentions = tuple(
            " ".join(match.group(0).split()) for match in _QUANTITY_RE.finditer(title)
        )
        bulk_terms: list[str] = []
        if _BULK_RE.search(title):
            bulk_terms.append("bulk_wording")
        if quantity_mentions:
            bulk_terms.append("documented_multi_unit_quantity")
        bulk_evidence = bool(bulk_terms)
        lots.append(
            DpvCatalogLot(
                object_id=object_id,
                canonical_url=group["identity"].canonical_url,
                title=title,
                listing_status=listing_status,
                clothing_evidence=clothing_evidence,
                clothing_terms=clothing_terms,
                bulk_evidence=bulk_evidence,
                bulk_terms=tuple(bulk_terms),
                quantity_mentions=quantity_mentions,
                ordinary_single_garment=bool(clothing_evidence and not bulk_evidence),
                exact_item_verified=False,
                exact_item_verification_error=None,
                source_displayed_amount_eur=None,
                source_displayed_amount_kind=None,
                source_bid_count=None,
                location=None,
                promotion_eligible=False,
                opportunity_identity=f"dpv-object:{object_id}",
                parent_opportunity_identity=parent_opportunity_identity,
            )
        )
    return tuple(lots)


def crawl_dpv_catalog(
    entry: DpvAuctionIndexEntry,
    *,
    session: Any | None = None,
    timeout: float = 20.0,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    catalog_page_limit: int = DEFAULT_CATALOG_PAGE_LIMIT,
    item_verification_limit: int = DEFAULT_ITEM_VERIFICATION_LIMIT,
) -> DpvCatalogCrawlResult:
    if entry.listing_status != ACTIVE:
        raise ValueError("only active DPV catalog entries may be crawled")
    if not 1 <= catalog_page_limit <= 200:
        raise ValueError("catalog_page_limit must be between 1 and 200")
    if not 0 <= item_verification_limit <= 100:
        raise ValueError("item_verification_limit must be between 0 and 100")

    first_page = fetch_dpv_catalog_page(
        entry.catalog_url,
        catalog_block_id=entry.catalog_block_id,
        session=session,
        timeout=timeout,
        max_response_bytes=max_response_bytes,
    )
    title, location, expected_page_count, total_results, heading_terms, full_scope = (
        _catalog_metadata(entry, first_page.html)
    )
    page_limit_reached = expected_page_count > catalog_page_limit
    target_page_count = min(expected_page_count, catalog_page_limit)
    page_urls = _extract_catalog_page_urls(
        entry.catalog_url,
        first_page.html,
        catalog_block_id=entry.catalog_block_id,
        expected_page_count=target_page_count,
    )
    page_diagnostics: list[dict[str, Any]] = [first_page.diagnostics()]
    page_errors: list[dict[str, Any]] = []
    lots_by_object: dict[str, DpvCatalogLot] = {}

    def absorb(page: DpvPublicPage) -> None:
        for lot in parse_dpv_catalog_lots(
            entry.catalog_url,
            page.html,
            listing_status=ACTIVE,
            parent_opportunity_identity=entry.opportunity_identity,
            full_catalog_clothing_scope=full_scope,
        ):
            lots_by_object.setdefault(lot.object_id, lot)

    absorb(first_page)
    for page_number in range(2, target_page_count + 1):
        page_url = page_urls[page_number]
        try:
            page = fetch_dpv_catalog_page(
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

    clothing_lots = [lot for lot in lots_by_object.values() if lot.clothing_evidence]
    verification_errors: list[dict[str, Any]] = []
    bulk_indexes = [
        index for index, lot in enumerate(clothing_lots) if lot.bulk_evidence
    ][:item_verification_limit]
    for index in bulk_indexes:
        lot = clothing_lots[index]
        try:
            page = fetch_dpv_item_page(
                lot.canonical_url,
                object_id=lot.object_id,
                session=session,
                timeout=timeout,
                max_response_bytes=max_response_bytes,
            )
            metadata = parse_dpv_item_metadata(lot.canonical_url, page.html)
            item_status = metadata.listing_status
            if item_status == UNKNOWN:
                item_status = ACTIVE
            verified = bool(
                metadata.clothing_evidence
                and metadata.bulk_evidence
                and item_status == ACTIVE
            )
            clothing_lots[index] = replace(
                lot,
                title=metadata.title or lot.title,
                listing_status=item_status,
                clothing_evidence=metadata.clothing_evidence,
                clothing_terms=metadata.clothing_terms,
                bulk_evidence=metadata.bulk_evidence,
                bulk_terms=metadata.bulk_terms,
                quantity_mentions=metadata.quantity_mentions,
                ordinary_single_garment=False,
                exact_item_verified=verified,
                source_displayed_amount_eur=metadata.displayed_amount_eur,
                source_displayed_amount_kind=metadata.displayed_amount_kind,
                source_bid_count=metadata.bid_count,
                location=metadata.location,
                promotion_eligible=False,
            )
        except Exception as exc:
            verification_errors.append(
                {
                    "object_id": lot.object_id,
                    "url": lot.canonical_url,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            clothing_lots[index] = replace(
                lot,
                exact_item_verification_error=str(exc),
            )

    contiguous_complete = (
        not page_limit_reached
        and not page_errors
        and len(page_diagnostics) == expected_page_count
    )
    result_count_complete = total_results is None or len(lots_by_object) == total_results
    coverage_complete = contiguous_complete and result_count_complete
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

    explicit_terms = _unique(
        list(entry.clothing_terms)
        + list(heading_terms)
        + [term for lot in clothing_lots for term in lot.clothing_terms]
    )
    explicit_clothing = bool(entry.clothing_evidence or heading_terms or clothing_lots)
    return DpvCatalogCrawlResult(
        index_entry=entry,
        title=title,
        location=location,
        listing_status=ACTIVE,
        page_diagnostics=tuple(page_diagnostics),
        page_errors=tuple(page_errors),
        item_verification_errors=tuple(verification_errors),
        catalog_page_urls=tuple(page_urls[number] for number in sorted(page_urls)),
        catalog_pages_fetched=len(page_diagnostics),
        catalog_page_limit=catalog_page_limit,
        catalog_page_limit_reached=page_limit_reached,
        catalog_coverage_complete=coverage_complete,
        catalog_coverage_reason=coverage_reason,
        catalog_total_results=total_results,
        catalog_expected_page_count=expected_page_count,
        catalog_item_url_count=len(lots_by_object),
        clothing_lots=tuple(clothing_lots),
        ordinary_child_lot_count=sum(lot.ordinary_single_garment for lot in clothing_lots),
        observed_bulk_lot_count=sum(lot.bulk_evidence for lot in clothing_lots),
        verified_bulk_lot_count=sum(lot.exact_item_verified for lot in clothing_lots),
        explicit_clothing_evidence=explicit_clothing,
        explicit_clothing_terms=explicit_terms,
        full_catalog_clothing_scope=full_scope,
    )


def _candidate_from_catalog(crawl: DpvCatalogCrawlResult) -> dict[str, Any]:
    unverified_bulk_urls = [
        lot.canonical_url
        for lot in crawl.clothing_lots
        if lot.bulk_evidence and not lot.exact_item_verified
    ]
    verified_bulk_urls = [
        lot.canonical_url for lot in crawl.clothing_lots if lot.exact_item_verified
    ]
    if verified_bulk_urls:
        next_step = (
            "Retain the exact verified bulk item evidence and keep the source blocked "
            "from Top 5 until live main-branch activation is approved."
        )
    elif unverified_bulk_urls:
        next_step = "Verify observed bulk clothing lots on their exact public item pages."
    else:
        next_step = "Keep watching; no explicit commercial bulk clothing lot is currently present."
    confirmed = [
        "source: Deutsche Pfandverwertung",
        f"catalog block: {crawl.index_entry.catalog_block_id}",
        f"auction identity: {crawl.opportunity_identity}",
        f"catalog pages fetched: {crawl.catalog_pages_fetched}",
        f"catalog items observed: {crawl.catalog_item_url_count}",
        f"clothing child lots observed: {len(crawl.clothing_lots)}",
        f"bulk clothing lots observed: {crawl.observed_bulk_lot_count}",
        f"bulk clothing lots exactly verified: {crawl.verified_bulk_lot_count}",
    ]
    if crawl.location:
        confirmed.append(f"location: {crawl.location}")
    return {
        "title": crawl.title,
        "scenario": "AUCTION",
        "opportunity_state": STRONG_LEAD_REQUIRES_VERIFICATION,
        "reason": (
            "verified Deutsche Pfandverwertung clothing auction event retained "
            "as one parent opportunity with child lots"
        ),
        "page_role": "AUCTION_EVENT",
        "opportunity_identity": crawl.opportunity_identity,
        "identity_stable": True,
        "top5_eligible": False,
        "analysis_eligible": False,
        "listing_status": crawl.listing_status,
        "market_code": "DE",
        "currency": "EUR",
        "location": crawl.location,
        "company_name": None,
        "inventory_type": "clothing_auction_event",
        "price": None,
        "price_nok": None,
        "bid_price_nok": None,
        "quantity": None,
        "source_urls": [crawl.index_entry.catalog_url],
        "source_providers": ["Deutsche Pfandverwertung"],
        "aggregation_mode": AGGREGATION_MODE,
        "child_lot_count": len(crawl.clothing_lots),
        "ordinary_child_lot_count": crawl.ordinary_child_lot_count,
        "observed_bulk_lot_count": crawl.observed_bulk_lot_count,
        "verified_bulk_lot_count": crawl.verified_bulk_lot_count,
        "promoted_bulk_lot_count": 0,
        "bulk_item_urls_requiring_verification": unverified_bulk_urls,
        "verified_bulk_item_urls": verified_bulk_urls,
        "child_lots": [lot.to_dict() for lot in crawl.clothing_lots],
        "confirmed_information": confirmed,
        "missing_information": [
            "source activation after current live clothing validation on main",
            "cross-border logistics basis",
            "documented final payable price",
        ],
        "next_verification_step": next_step,
        "next_action": "Retain the auction parent; do not publish a Top 5 item while the source is PLANNED.",
        "verification": [
            {
                "url": crawl.index_entry.catalog_url,
                "title": crawl.title,
                "text": None,
                "location": crawl.location,
                "inventory_type": "clothing_auction_event",
                "price_nok": None,
                "bid_price_nok": None,
                "quantity": None,
                "published_at": None,
                "listing_status": crawl.listing_status,
                "page_role": "AUCTION_EVENT",
                "opportunity_identity": crawl.opportunity_identity,
                "identity_stable": True,
                "clothing_inventory_evidence": True,
                "sale_evidence": True,
                "event_scenario": "AUCTION",
                "bounded_context": (
                    f"{crawl.title} | pages: {crawl.catalog_pages_fetched} | "
                    f"items: {crawl.catalog_item_url_count} | clothing lots: "
                    f"{len(crawl.clothing_lots)} | verified bulk lots: "
                    f"{crawl.verified_bulk_lot_count}"
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
        "post_verification_top5_block_reason": "source_not_active",
    }


def run_dpv_active_clothing_watch(
    index_url: str = DEFAULT_DPV_INDEX_URL,
    *,
    session: Any | None = None,
    timeout: float = 20.0,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    catalog_limit: int = DEFAULT_ACTIVE_CATALOG_LIMIT,
    catalog_page_limit: int = DEFAULT_CATALOG_PAGE_LIMIT,
    item_verification_limit: int = DEFAULT_ITEM_VERIFICATION_LIMIT,
) -> DpvActiveWatchResult:
    """Inspect current public catalogs and emit only verified clothing parents."""
    if not 1 <= catalog_limit <= 25:
        raise ValueError("catalog_limit must be between 1 and 25")
    if not 1 <= catalog_page_limit <= 200:
        raise ValueError("catalog_page_limit must be between 1 and 200")
    if not 0 <= item_verification_limit <= 100:
        raise ValueError("item_verification_limit must be between 0 and 100")

    index_page = fetch_dpv_auction_index(
        index_url,
        session=session,
        timeout=timeout,
        max_response_bytes=max_response_bytes,
    )
    entries = parse_dpv_auction_index(index_page.final_url, index_page.html)
    active_entries = [entry for entry in entries if entry.listing_status == ACTIVE]
    selected_entries = active_entries[:catalog_limit]

    catalog_runs: list[DpvCatalogCrawlResult] = []
    catalog_errors: list[dict[str, Any]] = []
    for entry in selected_entries:
        try:
            crawl = crawl_dpv_catalog(
                entry,
                session=session,
                timeout=timeout,
                max_response_bytes=max_response_bytes,
                catalog_page_limit=catalog_page_limit,
                item_verification_limit=item_verification_limit,
            )
            if not crawl.catalog_coverage_complete:
                raise RuntimeError(
                    "DPV catalog coverage incomplete: "
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
    item_verification_errors = [
        error for run in catalog_runs for error in run.item_verification_errors
    ]
    total_items = sum(run.catalog_item_url_count for run in catalog_runs)
    total_clothing_lots = sum(len(run.clothing_lots) for run in clothing_runs)
    total_observed_bulk = sum(run.observed_bulk_lot_count for run in clothing_runs)
    total_verified_bulk = sum(run.verified_bulk_lot_count for run in clothing_runs)
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
        "catalog_item_url_count": total_items,
        "clothing_child_lot_count": total_clothing_lots,
        "ordinary_child_lot_count": sum(
            run.ordinary_child_lot_count for run in clothing_runs
        ),
        "observed_bulk_lot_count": total_observed_bulk,
        "verified_bulk_lot_count": total_verified_bulk,
        "promoted_bulk_lot_count": 0,
        "single_garment_candidate_count": 0,
        "item_verification_limit": item_verification_limit,
        "item_verification_error_count": len(item_verification_errors),
        "index_entries": [entry.to_dict() for entry in entries],
        "selected_catalogs": [entry.to_dict() for entry in selected_entries],
        "catalog_runs": [run.diagnostics() for run in catalog_runs],
        "catalog_errors": catalog_errors,
        "item_verification_errors": item_verification_errors,
        "nok_price_fields_written": False,
        "normalized_price_written": False,
        "zero_clothing_results_are_valid": True,
    }
    all_errors = catalog_errors + item_verification_errors
    status = "PASS" if not all_errors else "PARTIAL"
    report = {
        "schema_version": "clothing-inventory-discovery-search-1.3",
        "domain": "CLOTHING_INVENTORY",
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "provider": "Deutsche Pfandverwertung active public catalog watch",
        "queries_submitted": 0,
        "query_matrix": [],
        "hits_received": len(entries) + total_items,
        "unique_public_urls": len(entries) + total_items,
        "merged_candidates": len(candidates),
        "duplicates_merged": 0,
        "rejected_results": len(entries) - len(clothing_runs),
        "confirmed_sales": 0,
        "strong_leads_requiring_verification": len(candidates),
        "ended_or_historical": sum(entry.listing_status == ENDED for entry in entries),
        "sources_discovered": 1,
        "discovery_bands": {"HIGH": 0, "REVIEW": len(candidates), "LOW": 0},
        "verification_attempted": bool(selected_entries),
        "verification_limit": item_verification_limit,
        "top5_count": 0,
        "top5_eligible_count": 0,
        "generic_pages_excluded": len(entries) - len(clothing_runs),
        "verification_failures": len(all_errors),
        "false_positive_guard_triggered": 0,
        "errors": all_errors,
        "execution_status": status,
        "opportunity_quality_status": (
            "LEADS_REQUIRING_VERIFICATION" if candidates else "NO_VALID_OPPORTUNITIES"
        ),
        "status": status,
        "no_opportunities_found": not candidates,
        "automatic_contact": False,
        "automatic_purchase_decision": False,
        "financial_ranking_used": False,
        "source_mode": "DPV_ACTIVE_WATCH",
        "source_target": "DEUTSCHE_PFANDVERWERTUNG_ACTIVE_AUCTIONS",
        "query_pack": "DPV_ACTIVE_INDEX_V1",
        "market_code": "DE",
        "currency": "EUR",
        "currency_conversion_performed": False,
        "tax_calculation_performed": False,
        "customs_calculation_performed": False,
        "logistics_calculation_performed": False,
        "source_adapter": {
            "source": "Deutsche Pfandverwertung",
            "market_code": "DE",
            "currency": "EUR",
            "aggregation_mode": AGGREGATION_MODE,
            "parent_candidate_count": len(candidates),
            "child_lot_count": total_clothing_lots,
            "observed_bulk_lot_count": total_observed_bulk,
            "verified_bulk_lot_count": total_verified_bulk,
            "promoted_bulk_candidate_count": 0,
            "single_garment_candidate_count": 0,
            "nok_price_fields_written": False,
            "normalized_price_written": False,
        },
        "dpv_active": diagnostics,
    }
    discovery = {
        "all_discovered_candidates": candidates,
        "discovery_top5": [],
        "source_adapter": report["source_adapter"],
        "search_run_report": report,
    }
    return DpvActiveWatchResult(discovery_result=discovery, diagnostics=diagnostics)
