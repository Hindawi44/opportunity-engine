"""Bounded live public-page fetch and verification for Riegermann.

Only exact public auction and item pages are fetched. The live layer does not
log in, bid, contact a seller, purchase, pay, bypass access controls, convert
EUR to NOK, or calculate VAT, buyer premium, customs, logistics, profit, or ROI.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.parse import urljoin

import requests

from opportunity_engine.discovery.clothing_inventory_search import ACTIVE
from opportunity_engine.discovery.germany_riegermann import (
    AGGREGATION_MODE,
    AUCTION_EVENT,
    RiegermannAuctionEvent,
    RiegermannChildLot,
    build_riegermann_adapter_result,
    canonicalize_riegermann_url,
    parse_riegermann_catalog_html,
    parse_riegermann_item_html,
)

DEFAULT_USER_AGENT = "OpportunityEngine-Riegermann-Pilot/1.0"
DEFAULT_MAX_RESPONSE_BYTES = 8_000_000
_ITEM_LINK_RE = re.compile(
    r"href\s*=\s*[\"'](?P<href>/de/l/(?P<object_id>[0-9]+)/[^\"'?#]+)[\"']",
    re.I,
)


class HttpResponse(Protocol):
    url: str
    status_code: int
    headers: Any
    content: bytes
    encoding: str | None

    def raise_for_status(self) -> None: ...


class HttpSession(Protocol):
    def get(self, url: str, **kwargs: Any) -> HttpResponse: ...


@dataclass(frozen=True, slots=True)
class RiegermannPublicPage:
    requested_url: str
    final_url: str
    canonical_url: str
    identity_kind: str
    auction_id: str | None
    object_id: str | None
    status_code: int
    content_type: str | None
    response_bytes: int
    sha256: str
    html: str

    def diagnostics(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("html", None)
        return data


@dataclass(frozen=True, slots=True)
class RiegermannLiveResult:
    discovery_result: dict[str, Any]
    diagnostics: dict[str, Any]


def fetch_riegermann_public_page(
    url: str,
    *,
    session: HttpSession | None = None,
    timeout: float = 20.0,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> RiegermannPublicPage:
    """Fetch one exact public Riegermann HTML page and fail closed on redirects."""
    requested_identity = canonicalize_riegermann_url(url)
    if requested_identity is None:
        raise ValueError("url must be an exact public Riegermann auction or item page")
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

    final_identity = canonicalize_riegermann_url(response.url)
    if final_identity is None:
        raise RuntimeError("Riegermann page redirected outside the exact public URL contract")
    if (
        requested_identity.kind,
        requested_identity.auction_id,
        requested_identity.object_id,
    ) != (
        final_identity.kind,
        final_identity.auction_id,
        final_identity.object_id,
    ):
        raise RuntimeError("Riegermann redirect changed auction or item identity")

    content_type = None
    if getattr(response, "headers", None):
        content_type = str(response.headers.get("content-type") or "").strip() or None
    if content_type and "html" not in content_type.casefold():
        raise RuntimeError(f"unexpected Riegermann content type: {content_type}")

    raw = bytes(response.content)
    if len(raw) > max_response_bytes:
        raise RuntimeError(f"Riegermann response exceeds {max_response_bytes} bytes")
    encoding = getattr(response, "encoding", None) or "utf-8"
    decoded = raw.decode(encoding, errors="replace")
    compact = decoded.casefold()
    if "<html" not in compact and "<!doctype html" not in compact:
        raise RuntimeError("Riegermann response is not an HTML document")
    if any(marker in compact for marker in ("captcha", "cloudflare challenge")):
        raise RuntimeError("Riegermann access challenge detected; no bypass attempted")

    return RiegermannPublicPage(
        requested_url=url,
        final_url=response.url,
        canonical_url=final_identity.canonical_url,
        identity_kind=final_identity.kind,
        auction_id=final_identity.auction_id,
        object_id=final_identity.object_id,
        status_code=int(response.status_code),
        content_type=content_type,
        response_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        html=decoded,
    )


def extract_riegermann_item_urls(
    catalog_url: str,
    source_html: str,
    *,
    limit: int = 1000,
) -> tuple[str, ...]:
    """Return unique exact public item URLs from one auction catalog."""
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


def _merge_information_event(
    catalog_event: RiegermannAuctionEvent,
    information_event: RiegermannAuctionEvent,
) -> RiegermannAuctionEvent:
    if catalog_event.auction_id != information_event.auction_id:
        raise ValueError("catalog and information pages refer to different auctions")
    return replace(
        catalog_event,
        title=information_event.title or catalog_event.title,
        listing_status=(
            information_event.listing_status
            if information_event.listing_status != "UNKNOWN"
            else catalog_event.listing_status
        ),
        scenario=information_event.scenario or catalog_event.scenario,
        location=information_event.location or catalog_event.location,
        auction_type=information_event.auction_type or catalog_event.auction_type,
        bidding_start_at=information_event.bidding_start_at or catalog_event.bidding_start_at,
        award_start_at=information_event.award_start_at or catalog_event.award_start_at,
        award_end_at=information_event.award_end_at or catalog_event.award_end_at,
        pickup_window=information_event.pickup_window or catalog_event.pickup_window,
        description=information_event.description or catalog_event.description,
        buyer_premium_percent=(
            information_event.buyer_premium_percent
            if information_event.buyer_premium_percent is not None
            else catalog_event.buyer_premium_percent
        ),
        vat_percent=(
            information_event.vat_percent
            if information_event.vat_percent is not None
            else catalog_event.vat_percent
        ),
    )


def _verification_for_parent(
    event: RiegermannAuctionEvent,
    catalog_page: RiegermannPublicPage,
    information_page: RiegermannPublicPage | None,
) -> dict[str, Any]:
    context_parts = [
        event.title,
        event.description,
        f"child lots observed: {len(event.child_lots)}",
        f"explicit bulk child lots: {len(event.promoted_bulk_lots)}",
    ]
    if event.location:
        context_parts.append(f"location: {event.location}")
    if event.buyer_premium_percent is not None:
        context_parts.append(f"source buyer premium: {event.buyer_premium_percent:g}%")
    if event.vat_percent is not None:
        context_parts.append(f"source VAT wording: {event.vat_percent:g}%")
    return {
        "url": catalog_page.canonical_url,
        "title": event.title,
        "text": event.description,
        "location": event.location,
        "inventory_type": "clothing_auction_event",
        "price_nok": None,
        "bid_price_nok": None,
        "quantity": None,
        "published_at": None,
        "listing_status": event.listing_status,
        "page_role": AUCTION_EVENT,
        "opportunity_identity": event.opportunity_identity,
        "identity_stable": True,
        "clothing_inventory_evidence": bool(event.child_lots),
        "sale_evidence": event.listing_status == ACTIVE,
        "event_scenario": event.scenario,
        "bounded_context": " | ".join(part for part in context_parts if part)[:5000],
        "verified": True,
        "error": None,
        "catalog_sha256": catalog_page.sha256,
        "information_sha256": information_page.sha256 if information_page else None,
    }


def _verification_for_lot(
    lot: RiegermannChildLot,
    page: RiegermannPublicPage,
) -> dict[str, Any]:
    context_parts = [lot.title, lot.description]
    if lot.quantity is not None:
        context_parts.append(f"quantity: {lot.quantity}")
    if lot.source_price_kind and lot.source_start_or_minimum_price_eur is not None:
        context_parts.append(
            f"source {lot.source_price_kind.lower()}: "
            f"{lot.source_start_or_minimum_price_eur:g} EUR"
        )
    if lot.source_displayed_bid_eur is not None:
        context_parts.append(
            f"source displayed bid: {lot.source_displayed_bid_eur:g} EUR "
            f"with {lot.source_bid_count} bids"
        )
    return {
        "url": page.canonical_url,
        "title": lot.title,
        "text": lot.description,
        "location": None,
        "inventory_type": (
            "commercial_clothing_bulk_lot"
            if lot.bulk_evidence
            else "single_clothing_item"
        ),
        "price_nok": None,
        "bid_price_nok": None,
        "quantity": lot.quantity,
        "published_at": None,
        "listing_status": lot.listing_status,
        "page_role": "ITEM_LISTING",
        "opportunity_identity": lot.opportunity_identity,
        "identity_stable": True,
        "clothing_inventory_evidence": lot.clothing_evidence and lot.bulk_evidence,
        "sale_evidence": lot.listing_status == ACTIVE and lot.bulk_evidence,
        "event_scenario": "LARGE_LOT_SALE",
        "bounded_context": " | ".join(part for part in context_parts if part)[:5000],
        "verified": True,
        "error": None,
        "response_sha256": page.sha256,
        "final_sale_price_trusted": lot.final_sale_price_trusted,
    }


def _attach_live_verification(
    discovery: dict[str, Any],
    *,
    event: RiegermannAuctionEvent,
    catalog_page: RiegermannPublicPage,
    information_page: RiegermannPublicPage | None,
    verified_lot_pages: dict[str, RiegermannPublicPage],
) -> None:
    for candidate in discovery["all_discovered_candidates"]:
        identity = candidate.get("opportunity_identity")
        if identity == event.opportunity_identity:
            candidate["verification"] = [
                _verification_for_parent(event, catalog_page, information_page)
            ]
            candidate["verification_content_match"] = True
            candidate["source_runtime_status"] = "PILOT"
            continue
        object_id = str(candidate.get("source_object_id") or "")
        page = verified_lot_pages.get(object_id)
        lot = next((item for item in event.child_lots if item.object_id == object_id), None)
        if page is None or lot is None:
            candidate["verification"] = []
            candidate["exact_item_page_verified"] = False
            continue
        candidate["verification"] = [_verification_for_lot(lot, page)]
        candidate["exact_item_page_verified"] = True
        candidate["verification_content_match"] = (
            lot.clothing_evidence and lot.bulk_evidence
        )
        candidate["source_runtime_status"] = "PILOT"


def run_riegermann_live_discovery(
    catalog_url: str,
    *,
    information_url: str | None = None,
    session: HttpSession | None = None,
    timeout: float = 20.0,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    item_verification_limit: int = 10,
) -> RiegermannLiveResult:
    """Fetch and verify one bounded public Riegermann auction event."""
    if item_verification_limit < 0 or item_verification_limit > 50:
        raise ValueError("item_verification_limit must be between 0 and 50")

    catalog_page = fetch_riegermann_public_page(
        catalog_url,
        session=session,
        timeout=timeout,
        max_response_bytes=max_response_bytes,
    )
    if catalog_page.identity_kind != "AUCTION_CATALOG":
        raise ValueError("catalog_url must resolve to an auction catalog")
    event = parse_riegermann_catalog_html(
        catalog_page.canonical_url,
        catalog_page.html,
    )
    item_urls = extract_riegermann_item_urls(
        catalog_page.canonical_url,
        catalog_page.html,
    )
    if not item_urls:
        raise RuntimeError("Riegermann catalog exposed no exact public item URLs")
    if not event.child_lots:
        raise RuntimeError(
            "Riegermann catalog item links were found but no child lots were parsed"
        )

    information_page: RiegermannPublicPage | None = None
    if information_url:
        information_page = fetch_riegermann_public_page(
            information_url,
            session=session,
            timeout=timeout,
            max_response_bytes=max_response_bytes,
        )
        if information_page.identity_kind != "AUCTION_INFORMATION":
            raise ValueError("information_url must resolve to auction information")
        information_event = parse_riegermann_catalog_html(
            information_page.canonical_url,
            information_page.html,
        )
        event = _merge_information_event(event, information_event)

    verified_lot_pages: dict[str, RiegermannPublicPage] = {}
    verified_lots: dict[str, RiegermannChildLot] = {}
    item_errors: list[dict[str, str]] = []
    for lot in event.promoted_bulk_lots[:item_verification_limit]:
        try:
            page = fetch_riegermann_public_page(
                lot.canonical_url,
                session=session,
                timeout=timeout,
                max_response_bytes=max_response_bytes,
            )
            parsed = parse_riegermann_item_html(
                page.canonical_url,
                page.html,
                auction_id=event.auction_id,
                fallback_status=event.listing_status,
            )
            if parsed.object_id != lot.object_id:
                raise RuntimeError("verified item page changed object identity")
            verified_lot_pages[lot.object_id] = page
            verified_lots[lot.object_id] = parsed
        except Exception as exc:
            item_errors.append(
                {
                    "object_id": lot.object_id,
                    "url": lot.canonical_url,
                    "error": str(exc),
                }
            )

    if verified_lots:
        event = replace(
            event,
            child_lots=tuple(
                verified_lots.get(lot.object_id, lot)
                for lot in event.child_lots
            ),
        )

    adapter = build_riegermann_adapter_result(event)
    discovery = adapter.to_discovery_result()
    _attach_live_verification(
        discovery,
        event=event,
        catalog_page=catalog_page,
        information_page=information_page,
        verified_lot_pages=verified_lot_pages,
    )

    candidates = discovery["all_discovered_candidates"]
    active_leads = sum(
        candidate.get("listing_status") == ACTIVE for candidate in candidates
    )
    report = {
        "schema_version": "clothing-inventory-discovery-search-1.3",
        "domain": "CLOTHING_INVENTORY",
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "provider": "Riegermann bounded public live adapter",
        "queries_submitted": 0,
        "query_matrix": [],
        "hits_received": 1 + len(item_urls),
        "unique_public_urls": 1 + len(item_urls),
        "merged_candidates": len(candidates),
        "duplicates_merged": 0,
        "rejected_results": 0,
        "confirmed_sales": 0,
        "strong_leads_requiring_verification": active_leads,
        "ended_or_historical": sum(
            candidate.get("listing_status") == "ENDED" for candidate in candidates
        ),
        "sources_discovered": 1,
        "discovery_bands": {"HIGH": 0, "REVIEW": len(candidates), "LOW": 0},
        "verification_attempted": True,
        "verification_limit": item_verification_limit,
        "top5_count": 0,
        "top5_eligible_count": 0,
        "generic_pages_excluded": 0,
        "verification_failures": len(item_errors),
        "false_positive_guard_triggered": 0,
        "errors": item_errors,
        "execution_status": "PASS",
        "opportunity_quality_status": "NO_VALID_OPPORTUNITIES",
        "status": "PASS",
        "no_opportunities_found": True,
        "automatic_contact": False,
        "automatic_purchase_decision": False,
        "financial_ranking_used": False,
        "source_mode": "RIEGERMANN",
        "source_target": f"RIEGERMANN_AUCTION_{event.auction_id}",
        "query_pack": "RIEGERMANN_BOUNDED_EVENT_V1",
        "market_code": "DE",
        "currency": "EUR",
        "currency_conversion_performed": False,
        "tax_calculation_performed": False,
        "customs_calculation_performed": False,
        "logistics_calculation_performed": False,
        "source_adapter": discovery["source_adapter"],
        "riegermann_live": {
            "auction_identity": event.opportunity_identity,
            "aggregation_mode": AGGREGATION_MODE,
            "catalog_page": catalog_page.diagnostics(),
            "information_page": (
                information_page.diagnostics() if information_page else None
            ),
            "catalog_item_url_count": len(item_urls),
            "parsed_child_lot_count": len(event.child_lots),
            "ordinary_child_lot_count": len(event.ordinary_child_lots),
            "promoted_bulk_lot_count": len(event.promoted_bulk_lots),
            "promoted_item_pages_requested": min(
                len(event.promoted_bulk_lots), item_verification_limit
            ),
            "promoted_item_pages_verified": len(verified_lot_pages),
            "item_verification_errors": item_errors,
            "single_garment_candidate_count": 0,
            "nok_price_fields_written": False,
            "normalized_price_written": False,
        },
    }
    discovery["search_run_report"] = report
    return RiegermannLiveResult(
        discovery_result=discovery,
        diagnostics=report["riegermann_live"],
    )
