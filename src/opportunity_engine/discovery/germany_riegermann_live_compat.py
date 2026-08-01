"""Compatibility helpers for current public Riegermann catalog markup.

The fixture-first parser remains unchanged. This module broadens only the live
catalog link shape (relative or absolute) and creates conservative child
evidence when the public catalog does not wrap items in fixture-style articles.
"""
from __future__ import annotations

import re
from dataclasses import replace
from urllib.parse import unquote, urljoin, urlparse

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
_CLOTHING_TERMS = (
    "bekleidung", "kleidung", "lederjacke", "ledermantel", "jacke",
    "mantel", "hose", "kleid", "rock", "schuhe", "stiefel", "bluse",
    "pullover", "mode",
)
_BULK_TERMS = (
    "posten", "konvolut", "sortiment", "warenbestand", "lagerbestand",
    "restposten", "paket",
)
_QUANTITY_RE = re.compile(
    r"\b(?P<count>[0-9]{1,7})\s*"
    r"(?:stück|stueck|stk|teile|jacken|mäntel|maentel|hosen|kleider|paar|artikel)\b",
    re.I,
)


def extract_riegermann_item_urls_compat(
    catalog_url: str,
    source_html: str,
    *,
    limit: int = 1000,
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
    event = fixture_parser.parse_riegermann_catalog_html(url, source_html)
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


def install_riegermann_live_catalog_compatibility() -> None:
    """Install the tested live compatibility functions for the CLI process."""
    live_layer.extract_riegermann_item_urls = extract_riegermann_item_urls_compat
    live_layer.parse_riegermann_catalog_html = parse_riegermann_catalog_html_compat
