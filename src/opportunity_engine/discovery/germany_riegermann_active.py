"""Discover active public Riegermann clothing auctions before catalog crawling.

This module reads only the public Riegermann auction index, identifies auction
entries with explicit clothing evidence, and delegates each selected auction to
the existing bounded catalog adapter. It does not log in, bid, contact sellers,
purchase, pay, bypass access controls, convert currencies, or calculate taxes,
customs, logistics, profit, or ROI.
"""
from __future__ import annotations

import hashlib
import html
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urljoin, urlparse, urlunparse

import requests

from opportunity_engine.discovery import germany_riegermann_live as live_layer
from opportunity_engine.discovery.clothing_inventory_search import ACTIVE
from opportunity_engine.discovery.germany_riegermann import (
    AGGREGATION_MODE,
    canonicalize_riegermann_url,
    map_riegermann_lifecycle,
)

DEFAULT_ACTIVE_AUCTIONS_URL = (
    "https://www.riegermann.de/de/Auktionen?Astatus=2&Atype2=2"
)
DEFAULT_ACTIVE_AUCTION_LIMIT = 5
DEFAULT_INDEX_MAX_RESPONSE_BYTES = 4_000_000

_H3_BLOCK_RE = re.compile(
    r"<h3\b[^>]*>(?P<title>.*?)</h3>(?P<body>.*?)(?=<h3\b|</main>|</body>|$)",
    re.I | re.S,
)
_ANCHOR_RE = re.compile(
    r"<a\b[^>]*href\s*=\s*[\"'](?P<href>[^\"']+)[\"'][^>]*>"
    r"(?P<label>.*?)</a>",
    re.I | re.S,
)
_LOCATION_RE = re.compile(
    r"\b(?P<location>DE-[0-9]{5}\s+.+?)"
    r"(?=\s+(?:Zuschläge|Verkauf eröffnet|Aktuell|Vorschau|Nachverkauf|"
    r"Abgeschlossen|Online-Katalog|Informationen)\b|$)",
    re.I,
)
_CLOTHING_TERMS = (
    "bekleidung",
    "kleidung",
    "lederbekleidung",
    "lederjacke",
    "lederjacken",
    "ledermantel",
    "ledermäntel",
    "lederhosen",
    "lederblazer",
    "textil",
    "textilien",
    "mode",
    "fashion",
    "konfektion",
    "boutique",
    "schuhe",
    "stiefel",
    "damenjacke",
    "herrenjacke",
    "kleider",
)


@dataclass(frozen=True, slots=True)
class RiegermannAuctionIndexPage:
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
class RiegermannAuctionIndexEntry:
    auction_id: str
    title: str
    catalog_url: str
    information_url: str | None
    listing_status: str
    location: str | None
    description: str | None
    clothing_evidence: bool
    clothing_terms: tuple[str, ...]

    @property
    def opportunity_identity(self) -> str:
        return f"riegermann-auction:{self.auction_id}"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["opportunity_identity"] = self.opportunity_identity
        return result


@dataclass(frozen=True, slots=True)
class RiegermannActiveDiscoveryResult:
    discovery_result: dict[str, Any]
    diagnostics: dict[str, Any]


def _normalized_host(host: str | None) -> str:
    value = (host or "").casefold()
    return value[4:] if value.startswith("www.") else value


def _strip_html(value: str) -> str:
    fragment = re.sub(
        r"<(script|style|noscript)\b[^>]*>.*?</\1>",
        " ",
        value,
        flags=re.I | re.S,
    )
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return " ".join(html.unescape(fragment).split())


def _validate_index_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("index_url must use HTTP or HTTPS")
    if _normalized_host(parsed.hostname) != "riegermann.de":
        raise ValueError("index_url must use the public Riegermann host")
    if not parsed.path.casefold().startswith("/de/auktionen"):
        raise ValueError("index_url must point to the public Riegermann auction index")


def fetch_riegermann_auction_index(
    url: str = DEFAULT_ACTIVE_AUCTIONS_URL,
    *,
    session: Any | None = None,
    timeout: float = 20.0,
    max_response_bytes: int = DEFAULT_INDEX_MAX_RESPONSE_BYTES,
) -> RiegermannAuctionIndexPage:
    """Fetch one public Riegermann auction-index page and fail closed."""
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
            "User-Agent": live_layer.DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    response.raise_for_status()
    _validate_index_url(str(response.url))

    content_type = None
    if getattr(response, "headers", None):
        content_type = str(response.headers.get("content-type") or "").strip() or None
    if content_type and "html" not in content_type.casefold():
        raise RuntimeError(f"unexpected Riegermann index content type: {content_type}")

    raw = bytes(response.content)
    if len(raw) > max_response_bytes:
        raise RuntimeError(f"Riegermann index exceeds {max_response_bytes} bytes")
    encoding = getattr(response, "encoding", None) or "utf-8"
    decoded = raw.decode(encoding, errors="replace")
    compact = decoded.casefold()
    if "<html" not in compact and "<!doctype html" not in compact:
        raise RuntimeError("Riegermann index response is not an HTML document")
    if any(marker in compact for marker in ("captcha", "cloudflare challenge")):
        raise RuntimeError("Riegermann access challenge detected; no bypass attempted")

    return RiegermannAuctionIndexPage(
        requested_url=url,
        final_url=str(response.url),
        status_code=int(response.status_code),
        content_type=content_type,
        response_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        html=decoded,
    )


def _preserve_catalog_query(url: str, canonical_url: str) -> str:
    parsed = urlparse(url)
    canonical = urlparse(canonical_url)
    return urlunparse(
        (
            "https",
            "riegermann.de",
            canonical.path,
            "",
            parsed.query,
            "",
        )
    )


def _entry_from_block(
    index_url: str,
    title_html: str,
    body_html: str,
) -> RiegermannAuctionIndexEntry | None:
    title = _strip_html(title_html).strip()
    catalog_url: str | None = None
    information_url: str | None = None
    auction_id: str | None = None

    for anchor in _ANCHOR_RE.finditer(body_html):
        href = html.unescape(anchor.group("href")).strip()
        if not href:
            continue
        candidate = urljoin(index_url, href)
        identity = canonicalize_riegermann_url(candidate)
        if identity is None or identity.auction_id is None:
            continue
        if identity.kind == "AUCTION_CATALOG":
            if auction_id is not None and identity.auction_id != auction_id:
                continue
            auction_id = identity.auction_id
            catalog_url = _preserve_catalog_query(candidate, identity.canonical_url)
        elif identity.kind == "AUCTION_INFORMATION":
            if auction_id is not None and identity.auction_id != auction_id:
                continue
            auction_id = identity.auction_id
            information_url = identity.canonical_url

    if auction_id is None or catalog_url is None:
        return None

    visible = _strip_html(f"{title_html} {body_html}")
    normalized = visible.casefold()
    matched_terms = tuple(
        term for term in _CLOTHING_TERMS if term in normalized
    )
    status = map_riegermann_lifecycle(visible)
    parsed_index = urlparse(index_url)
    if status == "UNKNOWN" and "astatus=2" in parsed_index.query.casefold():
        status = ACTIVE
    location_match = _LOCATION_RE.search(visible)
    location = (
        " ".join(location_match.group("location").split())
        if location_match
        else None
    )

    return RiegermannAuctionIndexEntry(
        auction_id=auction_id,
        title=title or f"Riegermann auction {auction_id}",
        catalog_url=catalog_url,
        information_url=information_url,
        listing_status=status,
        location=location,
        description=visible[:5000] or None,
        clothing_evidence=bool(matched_terms),
        clothing_terms=matched_terms,
    )


def parse_riegermann_auction_index(
    index_url: str,
    source_html: str,
) -> tuple[RiegermannAuctionIndexEntry, ...]:
    """Parse active auction entries and preserve one record per auction ID."""
    _validate_index_url(index_url)
    entries: list[RiegermannAuctionIndexEntry] = []
    seen: set[str] = set()

    for block in _H3_BLOCK_RE.finditer(source_html):
        entry = _entry_from_block(
            index_url,
            block.group("title"),
            block.group("body"),
        )
        if entry is None or entry.auction_id in seen:
            continue
        seen.add(entry.auction_id)
        entries.append(entry)

    if entries:
        return tuple(entries)

    # Conservative fallback for markup without h3 wrappers. Each catalog link gets
    # a bounded local context; entries without an exact catalog identity are ignored.
    for anchor in _ANCHOR_RE.finditer(source_html):
        href = html.unescape(anchor.group("href")).strip()
        candidate = urljoin(index_url, href)
        identity = canonicalize_riegermann_url(candidate)
        if (
            identity is None
            or identity.kind != "AUCTION_CATALOG"
            or identity.auction_id is None
            or identity.auction_id in seen
        ):
            continue
        start = max(0, anchor.start() - 5000)
        end = min(len(source_html), anchor.end() + 8000)
        entry = _entry_from_block(
            index_url,
            anchor.group("label"),
            source_html[start:end],
        )
        if entry is None:
            continue
        seen.add(entry.auction_id)
        entries.append(entry)
    return tuple(entries)


def _merge_candidates(
    destination: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    seen: set[str],
) -> None:
    for candidate in incoming:
        identity = str(candidate.get("opportunity_identity") or "")
        key = identity or str(candidate.get("source_urls") or candidate.get("title"))
        if key in seen:
            continue
        seen.add(key)
        destination.append(candidate)


def run_riegermann_active_auction_discovery(
    index_url: str = DEFAULT_ACTIVE_AUCTIONS_URL,
    *,
    session: Any | None = None,
    timeout: float = 20.0,
    max_response_bytes: int = live_layer.DEFAULT_MAX_RESPONSE_BYTES,
    item_verification_limit: int = 10,
    catalog_page_limit: int = 100,
    auction_limit: int = DEFAULT_ACTIVE_AUCTION_LIMIT,
    auction_runner: Callable[..., live_layer.RiegermannLiveResult] | None = None,
) -> RiegermannActiveDiscoveryResult:
    """Discover and crawl a bounded set of active clothing auction events."""
    if auction_limit < 1 or auction_limit > 25:
        raise ValueError("auction_limit must be between 1 and 25")
    if item_verification_limit < 0 or item_verification_limit > 50:
        raise ValueError("item_verification_limit must be between 0 and 50")
    if catalog_page_limit < 1 or catalog_page_limit > 200:
        raise ValueError("catalog_page_limit must be between 1 and 200")

    index_page = fetch_riegermann_auction_index(
        index_url,
        session=session,
        timeout=timeout,
        max_response_bytes=min(max_response_bytes, DEFAULT_INDEX_MAX_RESPONSE_BYTES),
    )
    entries = parse_riegermann_auction_index(index_page.final_url, index_page.html)
    clothing_entries = [
        entry
        for entry in entries
        if entry.clothing_evidence and entry.listing_status == ACTIVE
    ]
    selected_entries = clothing_entries[:auction_limit]
    runner = auction_runner or live_layer.run_riegermann_live_discovery

    candidates: list[dict[str, Any]] = []
    seen_candidates: set[str] = set()
    auction_runs: list[dict[str, Any]] = []
    auction_errors: list[dict[str, str]] = []
    total_catalog_items = 0
    total_child_lots = 0
    total_bulk_lots = 0

    for entry in selected_entries:
        try:
            live = runner(
                entry.catalog_url,
                information_url=entry.information_url,
                session=session,
                timeout=timeout,
                max_response_bytes=max_response_bytes,
                item_verification_limit=item_verification_limit,
                catalog_page_limit=catalog_page_limit,
            )
            result = live.discovery_result
            _merge_candidates(
                candidates,
                list(result.get("all_discovered_candidates") or []),
                seen_candidates,
            )
            diagnostics = dict(
                (result.get("search_run_report") or {}).get("riegermann_live")
                or live.diagnostics
                or {}
            )
            total_catalog_items += int(diagnostics.get("catalog_item_url_count") or 0)
            total_child_lots += int(diagnostics.get("parsed_child_lot_count") or 0)
            total_bulk_lots += int(diagnostics.get("promoted_bulk_lot_count") or 0)
            auction_runs.append(
                {
                    "auction_id": entry.auction_id,
                    "title": entry.title,
                    "catalog_url": entry.catalog_url,
                    "information_url": entry.information_url,
                    "status": "PASS",
                    "diagnostics": diagnostics,
                }
            )
        except Exception as exc:
            auction_errors.append(
                {
                    "auction_id": entry.auction_id,
                    "url": entry.catalog_url,
                    "error": str(exc),
                }
            )

    active_leads = sum(
        candidate.get("listing_status") == ACTIVE for candidate in candidates
    )
    ended_count = sum(
        candidate.get("listing_status") == "ENDED" for candidate in candidates
    )
    diagnostics = {
        "index_page": index_page.diagnostics(),
        "auction_entries_discovered": len(entries),
        "active_clothing_entries_discovered": len(clothing_entries),
        "selected_auction_count": len(selected_entries),
        "successful_auction_count": len(auction_runs),
        "failed_auction_count": len(auction_errors),
        "auction_limit": auction_limit,
        "auction_limit_reached": len(clothing_entries) > auction_limit,
        "catalog_item_url_count": total_catalog_items,
        "parsed_child_lot_count": total_child_lots,
        "promoted_bulk_lot_count": total_bulk_lots,
        "single_garment_candidate_count": 0,
        "index_entries": [entry.to_dict() for entry in entries],
        "selected_auctions": [entry.to_dict() for entry in selected_entries],
        "auction_runs": auction_runs,
        "auction_errors": auction_errors,
        "nok_price_fields_written": False,
        "normalized_price_written": False,
    }
    report = {
        "schema_version": "clothing-inventory-discovery-search-1.3",
        "domain": "CLOTHING_INVENTORY",
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "provider": "Riegermann active public auction discovery",
        "queries_submitted": 0,
        "query_matrix": [],
        "hits_received": len(entries) + total_catalog_items,
        "unique_public_urls": len(entries) + total_catalog_items,
        "merged_candidates": len(candidates),
        "duplicates_merged": 0,
        "rejected_results": len(entries) - len(clothing_entries),
        "confirmed_sales": 0,
        "strong_leads_requiring_verification": active_leads,
        "ended_or_historical": ended_count,
        "sources_discovered": 1,
        "discovery_bands": {"HIGH": 0, "REVIEW": len(candidates), "LOW": 0},
        "verification_attempted": bool(selected_entries),
        "verification_limit": item_verification_limit,
        "top5_count": 0,
        "top5_eligible_count": 0,
        "generic_pages_excluded": len(entries) - len(clothing_entries),
        "verification_failures": len(auction_errors),
        "false_positive_guard_triggered": 0,
        "errors": auction_errors,
        "execution_status": "PASS",
        "opportunity_quality_status": "NO_VALID_OPPORTUNITIES",
        "status": "PASS",
        "no_opportunities_found": True,
        "automatic_contact": False,
        "automatic_purchase_decision": False,
        "financial_ranking_used": False,
        "source_mode": "RIEGERMANN_ACTIVE",
        "source_target": "RIEGERMANN_ACTIVE_AUCTIONS",
        "query_pack": "RIEGERMANN_ACTIVE_INDEX_V1",
        "market_code": "DE",
        "currency": "EUR",
        "currency_conversion_performed": False,
        "tax_calculation_performed": False,
        "customs_calculation_performed": False,
        "logistics_calculation_performed": False,
        "source_adapter": {
            "source": "Riegermann",
            "market_code": "DE",
            "currency": "EUR",
            "aggregation_mode": AGGREGATION_MODE,
            "parent_candidate_count": sum(
                candidate.get("page_role") == "AUCTION_EVENT"
                for candidate in candidates
            ),
            "child_lot_count": total_child_lots,
            "promoted_bulk_candidate_count": total_bulk_lots,
            "single_garment_candidate_count": 0,
            "nok_price_fields_written": False,
            "normalized_price_written": False,
        },
        "riegermann_active": diagnostics,
    }
    discovery = {
        "all_discovered_candidates": candidates,
        "discovery_top5": [],
        "source_adapter": report["source_adapter"],
        "search_run_report": report,
    }
    return RiegermannActiveDiscoveryResult(
        discovery_result=discovery,
        diagnostics=diagnostics,
    )
