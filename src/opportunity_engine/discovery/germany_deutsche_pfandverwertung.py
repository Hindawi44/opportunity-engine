"""Bounded public-page primitives for Deutsche Pfandverwertung.

The adapter reads only the public auction index, catalog links and public item
pages. It never logs in, registers, bids, contacts sellers, purchases, pays,
bypasses access controls, converts currencies, or calculates tax, customs,
logistics, profit, or ROI.
"""
from __future__ import annotations

import hashlib
import html
import re
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import requests


DEFAULT_DPV_INDEX_URL = (
    "https://www.versteigerungen-deutsche-pfandverwertung.de/blocks_overview.php"
)
DEFAULT_MAX_RESPONSE_BYTES = 4_000_000
DEFAULT_USER_AGENT = (
    "opportunity-engine/deutsche-pfandverwertung-public-audit "
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
_H1_RE = re.compile(r"<h1\b[^>]*>(?P<title>.*?)</h1>", re.I | re.S)
_CATALOG_PATH_RE = re.compile(
    r"^/(?P<slug>.+)--search-1(?P<closed>-search_closed-y)?-block-"
    r"(?P<block_id>[0-9]+)-browse[.]html$",
    re.I,
)
_ITEM_PATH_RE = re.compile(
    r"^/(?P<section>[^/]+)/(?P<slug>.+)--id-(?P<object_id>[0-9]+)-item[.]html$",
    re.I,
)
_ITEM_COUNT_RE = re.compile(
    r"(?:Anzahl\s+Artikel|Quantity\s+items)\s*:\s*([0-9]+)",
    re.I,
)
_LOT_NUMBER_RE = re.compile(r"\bLos(?:nummer|-Nr[.]?)\s*:?[ ]*([0-9]+)\b", re.I)
_AMOUNT_RE = re.compile(
    r"\b(?P<label>Verkaufspreis|Startpreis|Sale\s+price|Starting\s+price)\s+"
    r"(?P<amount>[0-9][0-9. ]*(?:,[0-9]{2})?)\s*EUR\b",
    re.I,
)
_BID_COUNT_RE = re.compile(r"\b([0-9]+)\s+(?:Gebote|Bids)\b", re.I)
_LOCATION_RE = re.compile(
    r"\b(?:Ca[.]\s*)?Standort\s*:\s*(?P<location>.+?)"
    r"(?=\s+Dieser\s+Eintrag|\s+This\s+item|$)",
    re.I,
)
_QUANTITY_RE = re.compile(
    r"\b(?P<number>[0-9][0-9. ]*)\s*"
    r"(?P<unit>Paar|St(?:ü|ue)ck|Paletten|Packungen|Sets?|Artikel)\b",
    re.I,
)
_GENERIC_LABELS = {
    "",
    "katalog ansehen",
    "catalog view",
    "view catalog",
    "mehr",
    "more",
}
_CLOTHING_PATTERNS = (
    ("bekleidung", re.compile(r"bekleidung\w*", re.I)),
    ("kleidung", re.compile(r"(?<!be)kleidung\w*", re.I)),
    ("textilien", re.compile(r"textil\w*", re.I)),
    ("schuhe", re.compile(r"schuh\w*", re.I)),
    ("unterwaesche", re.compile(r"unterw(?:ä|ae)sche\w*", re.I)),
    ("jacken", re.compile(r"jacke\w*", re.I)),
    ("hosen", re.compile(r"hose\w*", re.I)),
    ("maentel", re.compile(r"m(?:ä|ae)ntel\w*", re.I)),
    ("schals", re.compile(r"schal\w*", re.I)),
    ("taschen", re.compile(r"tasche\w*", re.I)),
    ("socken", re.compile(r"socke\w*", re.I)),
    ("handschuhe", re.compile(r"handschuh\w*", re.I)),
    ("modewaren", re.compile(r"mode(?:waren|artikel|bestand)\w*", re.I)),
)
_BULK_PATTERNS = (
    ("konvolut", re.compile(r"(?:gro(?:ß|ss))?konvolut\w*", re.I)),
    ("sachgesamtheit", re.compile(r"sachgesamtheit\w*", re.I)),
    ("grossposten", re.compile(r"gro(?:ß|ss)e?\s+posten\w*", re.I)),
    ("warenbestand", re.compile(r"warenbestand\w*", re.I)),
    ("paletten", re.compile(r"\b[0-9][0-9. ]*\s+paletten\b", re.I)),
    ("multi_unit", re.compile(r"\b[0-9][0-9. ]*\s+(?:paar|st(?:ü|ue)ck|packungen)\b", re.I)),
)


@dataclass(frozen=True, slots=True)
class DpvUrlIdentity:
    kind: str
    canonical_url: str
    catalog_block_id: str | None = None
    object_id: str | None = None
    closed_catalog: bool = False


@dataclass(frozen=True, slots=True)
class DpvPublicPage:
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
class DpvAuctionIndexEntry:
    catalog_block_id: str
    title: str
    catalog_url: str
    listing_status: str
    item_count: int | None
    summary: str | None
    clothing_evidence: bool
    clothing_terms: tuple[str, ...]
    bulk_evidence: bool
    bulk_terms: tuple[str, ...]

    @property
    def opportunity_identity(self) -> str:
        return f"dpv-auction:{self.catalog_block_id}"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["opportunity_identity"] = self.opportunity_identity
        return result


@dataclass(frozen=True, slots=True)
class DpvItemMetadata:
    object_id: str
    title: str | None
    lot_number: str | None
    listing_status: str
    displayed_amount_eur: float | None
    displayed_amount_kind: str | None
    bid_count: int | None
    location: str | None
    quantity_mentions: tuple[str, ...]
    clothing_evidence: bool
    clothing_terms: tuple[str, ...]
    bulk_evidence: bool
    bulk_terms: tuple[str, ...]

    @property
    def opportunity_identity(self) -> str:
        return f"dpv-object:{self.object_id}"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["opportunity_identity"] = self.opportunity_identity
        return result


def _normalized_host(host: str | None) -> str:
    value = (host or "").casefold().rstrip(".")
    if value == "versteigerungen-deutsche-pfandverwertung.de":
        return "www.versteigerungen-deutsche-pfandverwertung.de"
    return value


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
    return urlunparse(
        (
            "https",
            "www.versteigerungen-deutsche-pfandverwertung.de",
            path,
            "",
            "",
            "",
        )
    )


def canonicalize_dpv_url(url: str) -> DpvUrlIdentity | None:
    """Return a bounded public Deutsche Pfandverwertung identity."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    if _normalized_host(parsed.hostname) != (
        "www.versteigerungen-deutsche-pfandverwertung.de"
    ):
        return None

    path = parsed.path or "/"
    if path in {"/", "/index.html", "/index.php", "/blocks_overview.php"}:
        return DpvUrlIdentity("AUCTION_INDEX", DEFAULT_DPV_INDEX_URL)

    catalog = _CATALOG_PATH_RE.fullmatch(path)
    if catalog:
        return DpvUrlIdentity(
            kind="AUCTION_CATALOG",
            canonical_url=_canonical_https(path),
            catalog_block_id=catalog.group("block_id"),
            closed_catalog=bool(catalog.group("closed")),
        )

    item = _ITEM_PATH_RE.fullmatch(path)
    if item:
        return DpvUrlIdentity(
            kind="ITEM_DETAIL",
            canonical_url=_canonical_https(path),
            object_id=item.group("object_id"),
        )
    return None


def map_dpv_lifecycle(text: str, *, closed_catalog: bool = False) -> str:
    normalized = " ".join(text.casefold().split())
    if closed_catalog or any(
        marker in normalized
        for marker in (
            "versteigerung beendet",
            "auktion beendet",
            "auction ended",
            "los ist verkauft",
            "lot was sold",
            "los wurde zurück genommen",
            "lot was withdrawn",
            "versteigerungstermin wurde abgesagt",
            "auction date has been cancelled",
        )
    ):
        return ENDED
    if any(
        marker in normalized
        for marker in (
            " live ",
            "beginn ",
            "versteigerung startet am",
            "auction starts on",
            "voraussichtliche aufrufzeit",
            "estimated call time",
        )
    ):
        return ACTIVE
    return UNKNOWN


def _matching_terms(
    text: str,
    patterns: tuple[tuple[str, re.Pattern[str]], ...],
) -> tuple[str, ...]:
    return tuple(label for label, pattern in patterns if pattern.search(text))


def _validate_index_url(url: str) -> None:
    identity = canonicalize_dpv_url(url)
    if identity is None or identity.kind != "AUCTION_INDEX":
        raise ValueError(
            "index_url must point to the public Deutsche Pfandverwertung auction index"
        )


def fetch_dpv_auction_index(
    url: str = DEFAULT_DPV_INDEX_URL,
    *,
    session: Any | None = None,
    timeout: float = 20.0,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> DpvPublicPage:
    """Fetch the public catalog overview with strict host, type and size checks."""
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
        raise RuntimeError(
            f"unexpected Deutsche Pfandverwertung index content type: {content_type}"
        )

    raw = bytes(response.content)
    if len(raw) > max_response_bytes:
        raise RuntimeError(
            f"Deutsche Pfandverwertung index exceeds {max_response_bytes} bytes"
        )
    encoding = getattr(response, "encoding", None) or "utf-8"
    decoded = raw.decode(encoding, errors="replace")
    compact = decoded.casefold()
    if "<html" not in compact and "<!doctype html" not in compact:
        raise RuntimeError("Deutsche Pfandverwertung index response is not HTML")
    if any(marker in compact for marker in ("cloudflare challenge", "access denied")):
        raise RuntimeError(
            "Deutsche Pfandverwertung access challenge detected; no bypass attempted"
        )

    return DpvPublicPage(
        requested_url=url,
        final_url=str(response.url),
        status_code=int(response.status_code),
        content_type=content_type,
        response_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        html=decoded,
    )


def parse_dpv_auction_index(
    index_url: str,
    source_html: str,
) -> tuple[DpvAuctionIndexEntry, ...]:
    """Parse one bounded index entry per public catalog block."""
    _validate_index_url(index_url)
    grouped: dict[str, dict[str, Any]] = {}

    for anchor in _ANCHOR_RE.finditer(source_html):
        candidate = urljoin(index_url, html.unescape(anchor.group("href")).strip())
        identity = canonicalize_dpv_url(candidate)
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
    archived_markers = [
        source_html.casefold().find("vergangene versteigerungen"),
        source_html.casefold().find("past auctions"),
    ]
    archived_marker = min((value for value in archived_markers if value >= 0), default=-1)
    entries: list[DpvAuctionIndexEntry] = []

    for index, group in enumerate(ordered):
        first_start = group["positions"][0][0]
        previous_end = ordered[index - 1]["positions"][-1][1] if index else 0
        next_start = (
            ordered[index + 1]["positions"][0][0]
            if index + 1 < len(ordered)
            else len(source_html)
        )
        context = source_html[previous_end:next_start]
        visible = _strip_html(context)
        labels = [
            label
            for label in group["labels"]
            if label.casefold() not in _GENERIC_LABELS
        ]
        identity: DpvUrlIdentity = group["identity"]
        title = max(labels, key=len) if labels else f"DPV catalog {identity.catalog_block_id}"
        item_count_match = _ITEM_COUNT_RE.search(visible)
        clothing_terms = _matching_terms(visible, _CLOTHING_PATTERNS)
        bulk_terms = _matching_terms(visible, _BULK_PATTERNS)
        closed = identity.closed_catalog or (
            archived_marker >= 0 and first_start > archived_marker
        )
        entries.append(
            DpvAuctionIndexEntry(
                catalog_block_id=str(identity.catalog_block_id),
                title=title,
                catalog_url=identity.canonical_url,
                listing_status=map_dpv_lifecycle(visible, closed_catalog=closed),
                item_count=(
                    int(item_count_match.group(1)) if item_count_match else None
                ),
                summary=visible[:5000] or None,
                clothing_evidence=bool(clothing_terms),
                clothing_terms=clothing_terms,
                bulk_evidence=bool(bulk_terms),
                bulk_terms=bulk_terms,
            )
        )
    return tuple(entries)


def _parse_eur(value: str) -> float:
    normalized = value.replace(" ", "").replace(".", "").replace(",", ".")
    return float(normalized)


def parse_dpv_item_metadata(
    item_url: str,
    source_html: str,
) -> DpvItemMetadata:
    """Parse stable item identity and source-native public observations."""
    identity = canonicalize_dpv_url(item_url)
    if identity is None or identity.kind != "ITEM_DETAIL" or identity.object_id is None:
        raise ValueError("item_url must be a public Deutsche Pfandverwertung item URL")

    visible = _strip_html(source_html)
    title_match = _H1_RE.search(source_html)
    title = _strip_html(title_match.group("title")) if title_match else None
    lot_match = _LOT_NUMBER_RE.search(visible)
    amount_match = _AMOUNT_RE.search(visible)
    bid_match = _BID_COUNT_RE.search(visible)
    location_match = _LOCATION_RE.search(visible)
    quantity_mentions = tuple(
        " ".join(match.group(0).split()) for match in _QUANTITY_RE.finditer(visible)
    )
    clothing_terms = _matching_terms(visible, _CLOTHING_PATTERNS)
    bulk_terms = _matching_terms(visible, _BULK_PATTERNS)

    amount_kind = None
    amount_eur = None
    if amount_match:
        amount_eur = _parse_eur(amount_match.group("amount"))
        label = amount_match.group("label").casefold()
        amount_kind = "FINAL_SALE_PRICE" if label in {"verkaufspreis", "sale price"} else "START_PRICE"

    return DpvItemMetadata(
        object_id=identity.object_id,
        title=title,
        lot_number=lot_match.group(1) if lot_match else None,
        listing_status=map_dpv_lifecycle(visible),
        displayed_amount_eur=amount_eur,
        displayed_amount_kind=amount_kind,
        bid_count=int(bid_match.group(1)) if bid_match else None,
        location=(
            " ".join(location_match.group("location").split())
            if location_match
            else None
        ),
        quantity_mentions=quantity_mentions,
        clothing_evidence=bool(clothing_terms),
        clothing_terms=clothing_terms,
        bulk_evidence=bool(bulk_terms),
        bulk_terms=bulk_terms,
    )
