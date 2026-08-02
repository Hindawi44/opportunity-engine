"""Bounded public-page primitives for VENTA Industrieversteigerungen.

This module intentionally stops at public index and catalog metadata parsing.
It never logs in, bids, contacts sellers, purchases, pays, bypasses access
controls, converts currencies, or calculates tax, customs, logistics, profit,
or ROI.
"""
from __future__ import annotations

import hashlib
import html
import re
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import requests


DEFAULT_VENTA_INDEX_URL = "https://auction.venta24.de/"
DEFAULT_MAX_RESPONSE_BYTES = 4_000_000
DEFAULT_USER_AGENT = (
    "opportunity-engine/venta-public-audit "
    "(+https://github.com/Hindawi44/opportunity-engine)"
)

ACTIVE = "ACTIVE"
ENDED = "ENDED"
UNKNOWN = "UNKNOWN"

_ANCHOR_RE = re.compile(
    r"<a\b[^>]*href\s*=\s*[\"'](?P<href>[^\"']+)[\"'][^>]*>"
    r"(?P<label>.*?)</a>",
    re.I | re.S,
)
_CATALOG_PATH_RE = re.compile(
    r"^/browse/search/1/block/(?P<slug>[^/]+)_(?P<block_id>[0-9]+)"
    r"(?P<closed>/search_closed/y)?\.html$",
    re.I,
)
_ITEM_PATH_RE = re.compile(
    r"^/item/id/(?P<catalog_number>[0-9]+)_(?P<lot_number>[0-9]+)_"
    r".+_(?P<object_id>[0-9]+)\.html$",
    re.I,
)
_AUCTION_NUMBER_RE = re.compile(r"\bAuktion\s+Nr\.?\s*([0-9]+)\b", re.I)
_TOTAL_RESULTS_RE = re.compile(r"\bObjekte\s+gesamt\s*:\s*([0-9]+)\b", re.I)
_PAGE_COUNT_RE = re.compile(r"\bSeite\s+[0-9]+\s+von\s+([0-9]+)\b", re.I)
_CATALOG_TITLE_RE = re.compile(
    r"\bAuktionskatalog\s+(?P<title>.+?)\s*\|\s*"
    r"[0-9]{2}\.[0-9]{2}\.[0-9]{4}",
    re.I,
)
_LOCATION_RE = re.compile(
    r"\bStandort\s*\|\s*(?P<location>.+?)"
    r"(?=\s+(?:Zur\s+Beachtung|Mehr/Weniger|Erster\s+Artikel\s+endet|$))",
    re.I,
)
_GENERIC_LABELS = {
    "",
    "katalog ansehen",
    "online-katalog",
    "online katalog",
    "mehr",
}
_CLOTHING_PATTERNS = (
    ("bekleidung", re.compile(r"\bbekleidung\w*\b", re.I)),
    ("kleidung", re.compile(r"\bkleidung\w*\b", re.I)),
    ("textilien", re.compile(r"\btextil(?:ien|waren|bestand)?\b", re.I)),
    ("modewaren", re.compile(r"\bmode(?:waren|bestand|artikel)\b", re.I)),
    ("konfektion", re.compile(r"\bkonfektion\w*\b", re.I)),
    ("schuhe", re.compile(r"\bschuh(?:e|waren|bestand)?\b", re.I)),
    ("lederbekleidung", re.compile(r"\bleder(?:bekleidung|jacken|hosen|maentel|mäntel)\b", re.I)),
    ("boutique", re.compile(r"\bboutique\b", re.I)),
)


@dataclass(frozen=True, slots=True)
class VentaUrlIdentity:
    kind: str
    canonical_url: str
    catalog_block_id: str | None = None
    catalog_number: str | None = None
    lot_number: str | None = None
    object_id: str | None = None
    closed_catalog: bool = False


@dataclass(frozen=True, slots=True)
class VentaPublicPage:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str | None
    response_bytes: int
    sha256: str
    html: str

    def diagnostics(self) -> dict[str, Any]:
        result = asdict(self)
        result.pop("html", None)
        return result


@dataclass(frozen=True, slots=True)
class VentaAuctionIndexEntry:
    catalog_block_id: str
    title: str
    catalog_url: str
    listing_status: str
    summary: str | None
    clothing_evidence: bool
    clothing_terms: tuple[str, ...]

    @property
    def provisional_identity(self) -> str:
        return f"venta-catalog-block:{self.catalog_block_id}"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["provisional_identity"] = self.provisional_identity
        return result


@dataclass(frozen=True, slots=True)
class VentaCatalogMetadata:
    catalog_block_id: str
    auction_number: str | None
    title: str | None
    listing_status: str
    location: str | None
    total_results: int | None
    page_count: int | None
    item_urls: tuple[str, ...]
    item_object_ids: tuple[str, ...]
    clothing_evidence: bool
    clothing_terms: tuple[str, ...]

    @property
    def opportunity_identity(self) -> str | None:
        if self.auction_number is None:
            return None
        return f"venta-auction:{self.auction_number}"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["opportunity_identity"] = self.opportunity_identity
        return result


def _normalized_host(host: str | None) -> str:
    return (host or "").casefold().rstrip(".")


def _strip_html(value: str) -> str:
    fragment = re.sub(
        r"<(script|style|noscript)\b[^>]*>.*?</\1>",
        " ",
        value,
        flags=re.I | re.S,
    )
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return " ".join(html.unescape(fragment).split())


def _canonical_https(path: str) -> str:
    return urlunparse(("https", "auction.venta24.de", path, "", "", ""))


def canonicalize_venta_url(url: str) -> VentaUrlIdentity | None:
    """Return a bounded public VENTA identity or reject the URL."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    if _normalized_host(parsed.hostname) != "auction.venta24.de":
        return None
    path = parsed.path or "/"
    if path in {"/", "/index.html"}:
        return VentaUrlIdentity("AUCTION_INDEX", DEFAULT_VENTA_INDEX_URL)

    catalog = _CATALOG_PATH_RE.fullmatch(path)
    if catalog:
        return VentaUrlIdentity(
            kind="AUCTION_CATALOG",
            canonical_url=_canonical_https(path),
            catalog_block_id=catalog.group("block_id"),
            closed_catalog=bool(catalog.group("closed")),
        )

    item = _ITEM_PATH_RE.fullmatch(path)
    if item:
        return VentaUrlIdentity(
            kind="ITEM_DETAIL",
            canonical_url=_canonical_https(path),
            catalog_number=item.group("catalog_number"),
            lot_number=item.group("lot_number"),
            object_id=item.group("object_id"),
        )
    return None


def map_venta_lifecycle(text: str, *, closed_catalog: bool = False) -> str:
    normalized = " ".join(text.casefold().split())
    if closed_catalog or "auktion beendet" in normalized:
        return ENDED
    if any(
        marker in normalized
        for marker in (
            "erster artikel endet",
            "beginn ",
            "auslauf der versteigerung",
        )
    ):
        return ACTIVE
    return UNKNOWN


def _matching_clothing_terms(text: str) -> tuple[str, ...]:
    return tuple(label for label, pattern in _CLOTHING_PATTERNS if pattern.search(text))


def _remove_title(text: str, title: str) -> str:
    if not title:
        return text
    return re.sub(re.escape(title), " ", text, flags=re.I)


def _validate_index_url(url: str) -> None:
    identity = canonicalize_venta_url(url)
    if identity is None or identity.kind != "AUCTION_INDEX":
        raise ValueError("index_url must point to the public VENTA auction index")


def fetch_venta_auction_index(
    url: str = DEFAULT_VENTA_INDEX_URL,
    *,
    session: Any | None = None,
    timeout: float = 20.0,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> VentaPublicPage:
    """Fetch the public index with strict host, type and size checks."""
    _validate_index_url(url)
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if max_response_bytes <= 0:
        raise ValueError("max_response_bytes must be positive")

    client = session or requests
    response = client.get(
        url,
        timeout=timeout,
        allow_redirects=True,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    response.raise_for_status()
    _validate_index_url(str(response.url))

    content_type = None
    if getattr(response, "headers", None):
        content_type = str(response.headers.get("content-type") or "").strip() or None
    if content_type and "html" not in content_type.casefold():
        raise RuntimeError(f"unexpected VENTA index content type: {content_type}")

    raw = bytes(response.content)
    if len(raw) > max_response_bytes:
        raise RuntimeError(f"VENTA index exceeds {max_response_bytes} bytes")
    encoding = getattr(response, "encoding", None) or "utf-8"
    decoded = raw.decode(encoding, errors="replace")
    compact = decoded.casefold()
    if "<html" not in compact and "<!doctype html" not in compact:
        raise RuntimeError("VENTA index response is not HTML")
    if any(marker in compact for marker in ("captcha", "cloudflare challenge")):
        raise RuntimeError("VENTA access challenge detected; no bypass attempted")

    return VentaPublicPage(
        requested_url=url,
        final_url=str(response.url),
        status_code=int(response.status_code),
        content_type=content_type,
        response_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        html=decoded,
    )


def parse_venta_auction_index(
    index_url: str,
    source_html: str,
) -> tuple[VentaAuctionIndexEntry, ...]:
    """Parse unique auction cards without using company names as clothing proof."""
    _validate_index_url(index_url)
    grouped: dict[str, dict[str, Any]] = {}

    for anchor in _ANCHOR_RE.finditer(source_html):
        candidate = urljoin(index_url, html.unescape(anchor.group("href")).strip())
        identity = canonicalize_venta_url(candidate)
        if identity is None or identity.kind != "AUCTION_CATALOG":
            continue
        block_id = str(identity.catalog_block_id)
        group = grouped.setdefault(
            block_id,
            {
                "identity": identity,
                "positions": [],
                "labels": [],
            },
        )
        group["positions"].append((anchor.start(), anchor.end()))
        label = _strip_html(anchor.group("label")).strip()
        if label:
            group["labels"].append(label)

    ordered = sorted(grouped.values(), key=lambda row: row["positions"][0][0])
    archived_marker = source_html.casefold().find("vergangene auktionen")
    entries: list[VentaAuctionIndexEntry] = []

    for index, group in enumerate(ordered):
        first_start = group["positions"][0][0]
        last_end = group["positions"][-1][1]
        previous_end = ordered[index - 1]["positions"][-1][1] if index else 0
        next_start = (
            ordered[index + 1]["positions"][0][0]
            if index + 1 < len(ordered)
            else len(source_html)
        )
        start = previous_end
        end = next_start
        context = source_html[start:end]
        visible = _strip_html(context)

        labels = [
            label
            for label in group["labels"]
            if label.casefold() not in _GENERIC_LABELS
        ]
        title = max(labels, key=len) if labels else f"VENTA catalog {group['identity'].catalog_block_id}"
        evidence_text = _remove_title(visible, title)
        matched_terms = _matching_clothing_terms(evidence_text)

        identity: VentaUrlIdentity = group["identity"]
        closed = identity.closed_catalog or (
            archived_marker >= 0 and first_start > archived_marker
        )
        status = map_venta_lifecycle(visible, closed_catalog=closed)
        entries.append(
            VentaAuctionIndexEntry(
                catalog_block_id=str(identity.catalog_block_id),
                title=title,
                catalog_url=identity.canonical_url,
                listing_status=status,
                summary=visible[:5000] or None,
                clothing_evidence=bool(matched_terms),
                clothing_terms=matched_terms,
            )
        )
    return tuple(entries)


def parse_venta_catalog_metadata(
    catalog_url: str,
    source_html: str,
) -> VentaCatalogMetadata:
    """Parse stable auction metadata and public item identities from one catalog."""
    identity = canonicalize_venta_url(catalog_url)
    if identity is None or identity.kind != "AUCTION_CATALOG":
        raise ValueError("catalog_url must be a public VENTA catalog URL")

    visible = _strip_html(source_html)
    auction_match = _AUCTION_NUMBER_RE.search(visible)
    title_match = _CATALOG_TITLE_RE.search(visible)
    total_match = _TOTAL_RESULTS_RE.search(visible)
    page_match = _PAGE_COUNT_RE.search(visible)
    location_match = _LOCATION_RE.search(visible)

    item_urls: list[str] = []
    item_ids: list[str] = []
    seen_items: set[str] = set()
    for anchor in _ANCHOR_RE.finditer(source_html):
        candidate = urljoin(catalog_url, html.unescape(anchor.group("href")).strip())
        item_identity = canonicalize_venta_url(candidate)
        if (
            item_identity is None
            or item_identity.kind != "ITEM_DETAIL"
            or item_identity.object_id is None
            or item_identity.object_id in seen_items
        ):
            continue
        seen_items.add(item_identity.object_id)
        item_urls.append(item_identity.canonical_url)
        item_ids.append(item_identity.object_id)

    title = " ".join(title_match.group("title").split()) if title_match else None
    matched_terms = _matching_clothing_terms(_remove_title(visible, title or ""))
    return VentaCatalogMetadata(
        catalog_block_id=str(identity.catalog_block_id),
        auction_number=auction_match.group(1) if auction_match else None,
        title=title,
        listing_status=map_venta_lifecycle(
            visible,
            closed_catalog=identity.closed_catalog,
        ),
        location=(
            " ".join(location_match.group("location").split())
            if location_match
            else None
        ),
        total_results=int(total_match.group(1)) if total_match else None,
        page_count=int(page_match.group(1)) if page_match else None,
        item_urls=tuple(item_urls),
        item_object_ids=tuple(item_ids),
        clothing_evidence=bool(matched_terms),
        clothing_terms=matched_terms,
    )
