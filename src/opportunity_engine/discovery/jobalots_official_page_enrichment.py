"""Bounded official-page enrichment for public Jobalots clothing lots."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import os
import re
import time
from typing import Any, Callable, Mapping
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from opportunity_engine.discovery.brave_market_signal_radar import (
    _canonical_url, _compact, _default_provider_factory, _iso_utc,
)
from opportunity_engine.discovery.jobalots_clothing_auction_feed import (
    _AUCTION_TERMS, _CONDITION_SOURCE_TERMS, _ENDED_TERMS, _MANIFEST_TERMS,
    _SOURCE_CLOTHING_TERMS, _SOURCE_COMMERCIAL_TERMS, _UNMANIFESTED_TERMS,
    _lot_size, _source_brands,
)
from opportunity_engine.discovery.merkandi_b2b_liquidation_feed import (
    _AUTHENTICITY_TERMS, _CLOTHING_TERMS, _COMMERCIAL_TERMS, _CONDITION_TERMS,
    _SHIPPING_TERMS, _matched_terms, _parse_number, _safety_payload,
)
from opportunity_engine.discovery.search_provider import SearchProvider

SCHEMA_VERSION = "jobalots-official-page-enrichment-1.0"
FEED_FAMILY = "B2B_OFFICIAL_PAGE_ENRICHMENT_V1"
SOURCE_NAME = "Jobalots"
APPROVED_DOMAINS = ("jobalots.com",)
APPROVED_PAGE_HOSTS = ("jobalots.com", "www.jobalots.com")
ROBOTS_URL = "https://jobalots.com/robots.txt"
DISCOVERY_QUERY = (
    'site:jobalots.com/en/products/ (clothing OR apparel OR footwear OR shoes) '
    '(pallet OR "job lot" OR liquidation OR returns OR overstock OR auction OR manifest)'
)
DEFAULT_RESULTS_PER_QUERY = 8
MAX_RESULTS_PER_QUERY = 10
DEFAULT_MAX_PAGES = 3
MAX_PAGES = 3
DEFAULT_FRESHNESS = "pm"
MAX_RESPONSE_BYTES = 2_000_000
MAX_CRAWL_DELAY_SECONDS = 10.0
ProviderFactory = Callable[[str, str, str | None], SearchProvider]

_MONEY = r"(?P<symbol>£|€|\$)?\s*(?P<amount>\d{1,12}(?:[\s.,]\d{3})*(?:[.,]\d{1,2})?)\s*(?P<code>GBP|EUR|USD)?"
_BID_RE = re.compile(rf"\bcurrent\s+bid\s*[:\-]?\s*{_MONEY}", re.I)
_RRP_RE = re.compile(rf"\b(?:reference\s+price|total\s+value|rrp|retail\s+value)\s*[:\-]?\s*{_MONEY}", re.I)
_RESERVE_RE = re.compile(rf"\breserve\s+price\s*[:\-]?\s*{_MONEY}", re.I)
_QTY_RE = re.compile(r"\b(?:lot\s+qty|total\s+quantity|quantity)\s*[:\-]?\s*(?P<n>\d{1,12}(?:[\s.,]\d{3})*)\b", re.I)
_WEIGHT_RE = re.compile(r"\bweight\s*[:\-]?\s*(?P<n>\d{1,9}(?:[\s.,]\d{3})*(?:[.,]\d{1,2})?)\s*\(?(?P<u>kg|kilograms?|lb|lbs|pounds?)\)?", re.I)
_SKU_RE = re.compile(r"\bSKU\s*[:\-]?\s*(?P<v>[A-Z0-9][A-Z0-9._-]{2,60})\b", re.I)
_VENDOR_RE = re.compile(r"\bVendor\s*[:\-]?\s*(?P<v>Jobalots(?:\s+(?:UK|EU|Europe))?)\b", re.I)
_LOCATION_RE = re.compile(r"\bLocation\s*[:\-]?\s*(?P<v>United\s+Kingdom|UK|Poland|Germany|Netherlands|France|Spain|Italy|Belgium|Ireland|Sweden|Denmark)\b", re.I)
_END_RE = re.compile(r"\b(?P<label>Ended\s+at|Ends?\s+at|Auction\s+ends?|Closing)\s*[:\-]?\s*(?P<v>[^|;<>]{4,80}?)\s*(?=(?:Current\s+bid|Details|Reference\s+price|Reserve\s+price|Type|Condition|Lot\s+Qty|Weight|Shipping|Vendor|Location|SKU|Manifest|Summary|$))", re.I)
_TYPE_RE = re.compile(r"\bType\s*[:\-]?\s*(?P<v>Pallets?|Boxes?|Lots?)\b", re.I)
_DELAY_RE = re.compile(r"(?im)^\s*Crawl-delay\s*:\s*([\d.]+)\s*$")


def _approved(url: str) -> str | None:
    try:
        url = _canonical_url(url)
    except ValueError:
        return None
    parts = urlsplit(url)
    path = parts.path.casefold().rstrip("/")
    if parts.scheme == "https" and (parts.hostname or "").casefold() in APPROVED_PAGE_HOSTS and path.startswith("/en/products/"):
        return url
    return None


def _currency(symbol: str | None, code: str | None) -> str | None:
    return _compact(code).upper() or {"£": "GBP", "€": "EUR", "$": "USD"}.get(symbol or "")


def _money(pattern: re.Pattern[str], text: str) -> tuple[float | None, str | None]:
    match = pattern.search(text)
    if not match:
        return None, None
    return _parse_number(match.group("amount")), _currency(match.group("symbol"), match.group("code"))


@dataclass(frozen=True, slots=True)
class FetchedPage:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    text: str
    bytes_read: int


class JobalotsPageFetcher:
    def __init__(self, timeout_seconds: float = 20.0) -> None:
        self.timeout_seconds = timeout_seconds

    def __call__(self, url: str) -> FetchedPage:
        if url != ROBOTS_URL and not _approved(url):
            raise ValueError("URL outside approved Jobalots page scope")
        request = Request(url, headers={"User-Agent": "OpportunityEngine/Jobalots-Page-Enrichment-1.0", "Accept": "text/plain" if url == ROBOTS_URL else "text/html"})
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise RuntimeError("response exceeded maximum byte limit")
            final_url = response.geturl() or url
            if url != ROBOTS_URL and not _approved(final_url):
                raise RuntimeError("redirect left approved Jobalots scope")
            return FetchedPage(url, final_url, int(getattr(response, "status", 200)), _compact(response.headers.get("Content-Type")), body.decode("utf-8", errors="replace"), len(body))


class _Parser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.ignore = 0
        self.h1 = False
        self.text: list[str] = []
        self.heading: list[str] = []
        self.meta: list[str] = []
        self.manifests: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k.casefold(): v or "" for k, v in attrs}
        if tag.casefold() in {"script", "style", "noscript", "svg", "template"}:
            self.ignore += 1
        elif tag.casefold() == "h1":
            self.h1 = True
        elif tag.casefold() == "meta" and attrs_dict.get("content"):
            self.meta.append(_compact(attrs_dict["content"]))
        elif tag.casefold() == "a" and "manifest" in attrs_dict.get("href", "").casefold():
            self.manifests.append(urljoin(self.base_url, attrs_dict["href"]))

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style", "noscript", "svg", "template"} and self.ignore:
            self.ignore -= 1
        elif tag.casefold() == "h1":
            self.h1 = False

    def handle_data(self, data: str) -> None:
        value = _compact(data)
        if not value or self.ignore:
            return
        self.text.append(value)
        if self.h1:
            self.heading.append(value)


def _document(html: str, url: str) -> tuple[str, str, list[str], str]:
    parser = _Parser(url)
    parser.feed(html)
    title = _compact(" ".join(parser.heading) or " ".join(parser.meta[:2]))[:1000]
    text = _compact(" ".join([*parser.meta, *parser.text]))[:250_000]
    return title, text, list(dict.fromkeys(parser.manifests))[:10], sha256(html.encode()).hexdigest()


def _robots(text: str) -> tuple[bool, float]:
    delay_match = _DELAY_RE.search(text)
    delay = float(delay_match.group(1)) if delay_match else 1.0
    active = False
    rules: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        if key.casefold() == "user-agent":
            active = value == "*"
        elif active and key.casefold() in {"allow", "disallow"} and value:
            rules.append((key.casefold(), value.rstrip("*")))
    matches = [(key, value) for key, value in rules if "/en/products/".startswith(value)]
    allowed = not matches or max(matches, key=lambda item: len(item[1]))[0] == "allow"
    return allowed, delay


def jobalots_page_candidate_from_html(*, source_url: str, html_text: str, observed_at: datetime) -> dict[str, Any] | None:
    url = _approved(source_url)
    if not url:
        return None
    title, text, manifest_urls, page_hash = _document(html_text, url)
    combined = _compact(f"{title} {text}")
    clothing = sorted(set(_matched_terms(combined, _CLOTHING_TERMS)) | set(_matched_terms(combined, _SOURCE_CLOTHING_TERMS)))
    commercial = sorted(set(_matched_terms(combined, _COMMERCIAL_TERMS)) | set(_matched_terms(combined, _SOURCE_COMMERCIAL_TERMS)))
    if not clothing or not commercial:
        return None
    bid, currency = _money(_BID_RE, combined)
    rrp, rrp_currency = _money(_RRP_RE, combined)
    reserve, reserve_currency = _money(_RESERVE_RE, combined)
    qty_match = _QTY_RE.search(combined)
    quantity = _parse_number(qty_match.group("n")) if qty_match else None
    weight_match = _WEIGHT_RE.search(combined)
    weight = _parse_number(weight_match.group("n")) if weight_match else None
    if weight is not None and weight_match and not weight_match.group("u").casefold().startswith("kg"):
        weight = round(weight * 0.45359237, 3)
    type_match = _TYPE_RE.search(combined)
    raw_type = type_match.group("v").casefold() if type_match else ""
    lot_type = "pallets" if raw_type.startswith("pallet") or "pallet" in title.casefold() else "boxes" if raw_type.startswith("box") else "lots" if raw_type else None
    sku = _SKU_RE.search(combined)
    vendor = _VENDOR_RE.search(combined)
    location_match = _LOCATION_RE.search(combined)
    location = _compact(location_match.group("v")) if location_match else None
    end_match = _END_RE.search(combined)
    end_text = _compact(end_match.group("v")) if end_match else None
    ended = bool(_matched_terms(combined, _ENDED_TERMS)) or bool(end_match and end_match.group("label").casefold().startswith("ended"))
    listing_status = "ENDED" if ended else "ACTIVE_REQUIRES_VERIFICATION"
    conditions = sorted(set(_matched_terms(combined, _CONDITION_TERMS)) | set(_matched_terms(combined, _CONDITION_SOURCE_TERMS)))
    manifests = _matched_terms(combined, _MANIFEST_TERMS)
    unmanifested = _matched_terms(combined, _UNMANIFESTED_TERMS)
    manifest_available = bool(manifest_urls or manifests) and not unmanifested
    shipping = _matched_terms(combined, _SHIPPING_TERMS)
    if "shipping details" in combined.casefold():
        shipping = sorted(set(shipping) | {"shipping details"})
    brands = _source_brands(combined)
    authenticity = _matched_terms(combined, _AUTHENTICITY_TERMS)
    missing = []
    for absent, name in ((quantity is None, "QUANTITY"), (bid is None, "CURRENT_BID"), (rrp is None, "REFERENCE_RETAIL_VALUE"), (not manifest_available, "MANIFEST_OR_ITEMISED_CONTENTS"), (not conditions, "CONDITION"), (not location, "WAREHOUSE_LOCATION"), (not shipping, "SHIPPING_TO_NORWAY"), (listing_status != "ENDED" and not end_text, "AUCTION_END_TIME")):
        if absent:
            missing.append(name)
    country = {"united kingdom": "GB", "uk": "GB", "poland": "PL", "germany": "DE"}.get((location or "").casefold())
    state = "B2B_LEAD_REQUIRES_VERIFICATION" if not ended and len(missing) <= 3 else "EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION"
    reference = sku.group("v") if sku else urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1][:80]
    return {
        "candidate_id": "jobalots-page:" + sha256(url.encode()).hexdigest()[:24],
        "feed_family": FEED_FAMILY, "source_name": SOURCE_NAME, "source_region": "UK_AND_EU",
        "source_country": country, "official_domain": (urlsplit(url).hostname or "").casefold(),
        "source_url": url, "source_reference": reference, "title": title or reference,
        "description": combined[:1500], "observed_at": _iso_utc(observed_at),
        "page_role": "OFFICIAL_SPECIFIC_AUCTION_OR_JOB_LOT_PAGE", "listing_status": listing_status,
        "sale_mode": "AUCTION", "inventory_focus": "CLOTHING_OR_FOOTWEAR_FOCUSED",
        "quantity": quantity, "quantity_unit": "items" if quantity is not None else None,
        "lot_units": 1.0 if lot_type else None, "lot_unit_type": lot_type,
        "lot_size_band": _lot_size(quantity, "items", 1.0 if lot_type else None),
        "current_bid": bid, "total_price": bid, "currency": currency,
        "estimated_retail_value": rrp, "estimated_retail_currency": rrp_currency or currency,
        "reserve_price": reserve, "reserve_currency": reserve_currency or currency,
        "weight_kg": weight, "condition_terms": conditions, "brands": brands,
        "stock_location": location, "auction_end_text": end_text,
        "manifest_available": manifest_available, "manifest_urls": manifest_urls,
        "manifest_terms": manifests, "unmanifested_terms": unmanifested,
        "authenticity_evidence_visible": bool(authenticity), "shipping_information_present": bool(shipping),
        "seller_name": _compact(vendor.group("v")) if vendor else SOURCE_NAME,
        "missing_information": missing, "opportunity_state": state,
        "verification_status": "OFFICIAL_PAGE_TEXT_EXTRACTED_REQUIRES_HUMAN_REVIEW",
        "page_sha256": page_hash, "source_evidence": [{"field": "official_page", "source_url": url, "page_sha256": page_hash}],
        "b2b_relevance_score": max(0, min(100, 55 + (10 if quantity else 0) + (10 if bid else 0) + (8 if rrp else 0) + (8 if manifest_available else 0) - (12 if ended else 0))),
        "decision_owner": "HUMAN_OPERATOR", "quantity_size_rejection_applied": False,
        "recommended_operator_action": "REVIEW_OFFICIAL_PAGE_MANIFEST_FEES_SHIPPING_AND_DECIDE_MANUALLY",
        **_safety_payload(),
    }


def collect_jobalots_official_page_enrichment(*, observed_at: datetime | None = None, environment: Mapping[str, str] | None = None, provider_factory: ProviderFactory = _default_provider_factory, page_fetcher: Callable[[str], FetchedPage] | None = None, sleep_fn: Callable[[float], None] = time.sleep, results_per_query: int = DEFAULT_RESULTS_PER_QUERY, max_pages: int = DEFAULT_MAX_PAGES, freshness: str | None = DEFAULT_FRESHNESS) -> dict[str, Any]:
    if not 1 <= results_per_query <= MAX_RESULTS_PER_QUERY or not 1 <= max_pages <= MAX_PAGES:
        raise ValueError("bounded query/page limits exceeded")
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    env = environment if environment is not None else os.environ
    key = _compact(env.get("BRAVE_SEARCH_API_KEY")) or _compact(env.get("BRAVE_API_KEY"))
    base = {
        "schema_version": SCHEMA_VERSION, "generated_at": _iso_utc(now), "feed_family": FEED_FAMILY,
        "purpose": "SOURCE_BACKED_JOBALOTS_PAGE_FIELD_ENRICHMENT_FOR_HUMAN_DECISION",
        "approved_official_domains": list(APPROVED_DOMAINS), "query_budget_total": 1,
        "page_limit": max_pages, "brave_requests_made": 0, "robots_requests_made": 0,
        "page_requests_made": 0, "requests_made": 0, "candidate_count": 0, "candidates": [],
        "discovered_official_url_count": 0, "errors": [], "quantity_size_rejection_enabled": False,
        "human_decision_required": True, "decision_owner": "HUMAN_OPERATOR", **_safety_payload(),
    }
    if not key:
        return {**base, "status_counts": {"BLOCKED_CONFIGURATION": 1}, "block_reason": "BRAVE_SEARCH_API_KEY_MISSING"}
    fetch = page_fetcher or JobalotsPageFetcher()
    try:
        provider = provider_factory("GB", key, freshness)
        hits = provider.search(DISCOVERY_QUERY, count=results_per_query)
        base["brave_requests_made"] = 1
        urls = sorted({url for hit in hits if (url := _approved(_compact(getattr(hit, "url", ""))))})
        base["discovered_official_url_count"] = len(urls)
        robots_page = fetch(ROBOTS_URL)
        base["robots_requests_made"] = 1
        allowed, delay = _robots(robots_page.text)
        base["crawl_delay_seconds"] = delay
        if not allowed:
            return {**base, "requests_made": 2, "status_counts": {"BLOCKED_ROBOTS": 1}, "block_reason": "ROBOTS_DISALLOWS_PRODUCT_PAGES"}
        if delay < 0 or delay > MAX_CRAWL_DELAY_SECONDS:
            return {**base, "requests_made": 2, "status_counts": {"BLOCKED_ROBOTS": 1}, "block_reason": "ROBOTS_CRAWL_DELAY_OUTSIDE_SAFE_RANGE"}
        candidates = []
        for url in urls[:max_pages]:
            sleep_fn(delay)
            page = fetch(url)
            base["page_requests_made"] += 1
            candidate = jobalots_page_candidate_from_html(source_url=page.final_url, html_text=page.text, observed_at=now)
            if candidate:
                candidate.update(page_http_status=page.status_code, page_content_type=page.content_type, page_bytes_read=page.bytes_read)
                candidates.append(candidate)
        base.update(candidate_count=len(candidates), candidates=candidates)
        status = "SUCCESS" if candidates else "VALID_ZERO"
        return {**base, "requests_made": base["brave_requests_made"] + base["robots_requests_made"] + base["page_requests_made"], "status_counts": {status: 1}, "block_reason": None}
    except Exception as exc:
        base["errors"].append(f"{type(exc).__name__}: {_compact(exc)[:300]}")
        return {**base, "requests_made": base["brave_requests_made"] + base["robots_requests_made"] + base["page_requests_made"], "status_counts": {"BLOCKED_RETRIEVAL": 1}, "block_reason": "DISCOVERY_OR_PAGE_RETRIEVAL_FAILED"}
