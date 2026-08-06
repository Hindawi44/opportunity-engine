"""Discover and enrich Stock-Hurt offers from fixed official catalogue pages.

This lane reads public official HTML only: robots.txt, two fixed catalogue pages,
and at most three official product pages. It never logs in or performs a commercial
action. Missing information and large lots remain visible for human decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import re
import time
from typing import Any, Callable, Mapping
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from opportunity_engine.discovery.brave_market_signal_radar import (
    _canonical_url,
    _compact,
    _iso_utc,
)
from opportunity_engine.discovery.merkandi_b2b_liquidation_feed import (
    _AUTHENTICITY_TERMS,
    _CLOTHING_TERMS,
    _COMMERCIAL_TERMS,
    _CONDITION_TERMS,
    _MANIFEST_TERMS,
    _SHIPPING_TERMS,
    _extract_inventory_quantity,
    _extract_location,
    _extract_price,
    _lot_size_band,
    _matched_terms,
    _safety_payload,
)
from opportunity_engine.discovery.stockhurt_b2b_feed import (
    _AUCTION_TERMS,
    _OUT_OF_STOCK_TERMS,
    _SOURCE_COMMERCIAL_TERMS,
    _extract_grade,
    _extract_minimum_order,
    _extract_source_brands,
    _extract_unit_hint,
)

SCHEMA_VERSION = "stockhurt-official-catalog-enrichment-1.0"
FEED_FAMILY = "STOCKHURT_OFFICIAL_CATALOG_ENRICHMENT_V1"
SOURCE_NAME = "Stock-Hurt"
SOURCE_COUNTRY = "PL"
APPROVED_DOMAINS = ("stockhurt.com",)
APPROVED_HOSTS = ("stockhurt.com", "www.stockhurt.com")
ROBOTS_URL = "https://stockhurt.com/robots.txt"
SHOP_URL = "https://stockhurt.com/en/shop/"
AUCTION_URL = "https://stockhurt.com/en/licytacje/"
CATALOG_URLS = (SHOP_URL, AUCTION_URL)
DEFAULT_MAX_CATALOG_PAGES = 2
MAX_CATALOG_PAGES = 2
DEFAULT_MAX_PRODUCT_PAGES = 3
MAX_PRODUCT_PAGES = 3
MAX_RESPONSE_BYTES = 2_000_000
MAX_CRAWL_DELAY_SECONDS = 10.0

_PRODUCT_PATH_RE = re.compile(
    r"(?:https?://(?:www\.)?stockhurt\.com)?"
    r"(?P<path>/en/product/[A-Za-z0-9._~!$&'()*+,;=:@%/-]+)",
    re.IGNORECASE,
)
_ESCAPED_PRODUCT_PATH_RE = re.compile(
    r"(?P<path>\\?/en\\?/product\\?/[A-Za-z0-9._~!$&'()*+,;=:@%/-]+)",
    re.IGNORECASE,
)
_DELAY_RE = re.compile(r"(?im)^\s*Crawl-delay\s*:\s*([\d.]+)\s*$")
_CURRENT_BID_RE = re.compile(
    r"\bcurrent\s+bid\s*[:\-]?\s*(?P<symbol>€|£|\$)?\s*"
    r"(?P<amount>\d{1,12}(?:[\s.,]\d{3})*(?:[.,]\d{1,2})?)\s*"
    r"(?P<code>PLN|EUR|GBP|USD)?",
    re.IGNORECASE,
)
_WEIGHT_RE = re.compile(
    r"\b(?:weight|net\s+weight)\s*[:\-]?\s*"
    r"(?P<amount>\d{1,9}(?:[\s.,]\d{3})*(?:[.,]\d{1,2})?)\s*"
    r"(?P<unit>kg|kilograms?|lb|lbs|pounds?)",
    re.IGNORECASE,
)
_SKU_RE = re.compile(
    r"\b(?:SKU|product\s+code)\s*[:\-]?\s*"
    r"(?P<value>[A-Z0-9][A-Z0-9._/-]{2,80})\b",
    re.IGNORECASE,
)
_AUCTION_END_RE = re.compile(
    r"\b(?:auction\s+ends?|bidding\s+ends?|closing)\s*[:\-]?\s*"
    r"(?P<value>[^|;<>]{4,100}?)\s*"
    r"(?=(?:current\s+bid|price|brand|grade|condition|weight|SKU|$))",
    re.IGNORECASE,
)
_CHALLENGE_TERMS = (
    "please wait while your request is being verified",
    "checking your browser before accessing",
    "enable javascript and cookies to continue",
    "cf-chl-",
    "challenge-platform",
)
_PACKING_TERMS = (
    "manifest",
    "packing list",
    "packing-list",
    "stock list",
    "stock-list",
    "item list",
)


def _parse_number(raw: str | None) -> float | None:
    value = _compact(raw)
    if not value:
        return None
    value = value.replace("\u00a0", "").replace(" ", "")
    if "," in value and "." in value:
        value = value.replace(",", "") if value.rfind(".") > value.rfind(",") else value.replace(".", "").replace(",", ".")
    elif "," in value:
        tail = value.rsplit(",", 1)[-1]
        value = value.replace(",", ".") if len(tail) <= 2 else value.replace(",", "")
    try:
        return float(value)
    except ValueError:
        return None


def _currency(symbol: str | None, code: str | None) -> str | None:
    explicit = _compact(code).upper()
    if explicit:
        return explicit
    return {"€": "EUR", "£": "GBP", "$": "USD"}.get(symbol or "")


def is_source_protection_challenge(html_text: str) -> bool:
    folded = html_text.casefold()
    return any(term in folded for term in _CHALLENGE_TERMS)


@dataclass(frozen=True, slots=True)
class FetchedPage:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    text: str
    bytes_read: int


@dataclass(frozen=True, slots=True)
class CatalogLink:
    url: str
    catalog_url: str
    catalog_scope: str
    context: str
    clothing_terms: tuple[str, ...]
    commercial_terms: tuple[str, ...]
    discovery_rank: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "catalog_url": self.catalog_url,
            "catalog_scope": self.catalog_scope,
            "context": self.context,
            "clothing_terms": list(self.clothing_terms),
            "commercial_terms": list(self.commercial_terms),
            "discovery_rank": self.discovery_rank,
        }


class StockhurtCatalogFetcher:
    """HTTP fetcher restricted to fixed Stock-Hurt public pages."""

    def __init__(self, timeout_seconds: float = 20.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = timeout_seconds

    def __call__(self, url: str) -> FetchedPage:
        if not _approved_fetch_url(url):
            raise ValueError("URL outside approved Stock-Hurt scope")
        request = Request(
            url,
            headers={
                "User-Agent": "OpportunityEngine/StockHurt-Catalog-Enrichment-1.0",
                "Accept": (
                    "text/plain,*/*;q=0.1"
                    if url == ROBOTS_URL
                    else "text/html,application/xhtml+xml"
                ),
                "Accept-Language": "en-GB,en;q=0.8",
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise RuntimeError("response exceeded maximum byte limit")
            final_url = response.geturl() or url
            if not _approved_fetch_url(final_url, allow_query_variants=True):
                raise RuntimeError("redirect left approved Stock-Hurt scope")
            return FetchedPage(
                requested_url=url,
                final_url=final_url,
                status_code=int(getattr(response, "status", 200)),
                content_type=_compact(response.headers.get("Content-Type")),
                text=body.decode("utf-8", errors="replace"),
                bytes_read=len(body),
            )


def _canonical_product_url(raw_url: str, *, base_url: str) -> str | None:
    absolute = urljoin(base_url, raw_url.replace("\\/", "/"))
    try:
        canonical = _canonical_url(absolute)
    except ValueError:
        return None
    parts = urlsplit(canonical)
    host = (parts.hostname or "").casefold().rstrip(".")
    path = parts.path.rstrip("/")
    if (
        parts.scheme != "https"
        or host not in APPROVED_HOSTS
        or not path.casefold().startswith("/en/product/")
        or path.casefold() == "/en/product"
    ):
        return None
    return f"https://stockhurt.com{path}/"


def _approved_fetch_url(url: str, *, allow_query_variants: bool = False) -> bool:
    if url == ROBOTS_URL or url in CATALOG_URLS:
        return True
    if _canonical_product_url(url, base_url="https://stockhurt.com/"):
        return True
    if not allow_query_variants:
        return False
    parts = urlsplit(url)
    host = (parts.hostname or "").casefold().rstrip(".")
    path = parts.path.rstrip("/").casefold()
    return (
        parts.scheme == "https"
        and host in APPROVED_HOSTS
        and path in {"/en/shop", "/en/licytacje"}
    )


class _CatalogParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self._active_href: str | None = None
        self._active_parts: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        values = {key.casefold(): value or "" for key, value in attrs}
        folded = tag.casefold()
        if folded == "a":
            self._active_href = values.get("href") or None
            self._active_parts = [
                values.get("title", ""),
                values.get("aria-label", ""),
                values.get("data-product-title", ""),
            ]
        elif folded == "img" and self._active_href:
            self._active_parts.extend(
                [values.get("alt", ""), values.get("title", "")]
            )

    def handle_data(self, data: str) -> None:
        if self._active_href:
            self._active_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a" and self._active_href:
            self.links.append(
                (self._active_href, _compact(" ".join(self._active_parts)))
            )
            self._active_href = None
            self._active_parts = []


def _scope_for_catalog(catalog_url: str) -> str:
    return "PALLET_AUCTIONS" if catalog_url == AUCTION_URL else "WHOLESALE_SHOP"


def discover_stockhurt_product_links(
    *,
    catalog_url: str,
    html_text: str,
) -> list[CatalogLink]:
    if catalog_url not in CATALOG_URLS:
        raise ValueError("catalog_url is outside fixed production scope")
    if is_source_protection_challenge(html_text):
        return []
    parser = _CatalogParser(catalog_url)
    parser.feed(html_text)
    contexts: dict[str, list[str]] = {}
    for raw_url, context in parser.links:
        canonical = _canonical_product_url(raw_url, base_url=catalog_url)
        if canonical:
            contexts.setdefault(canonical, []).append(context)
    for pattern in (_PRODUCT_PATH_RE, _ESCAPED_PRODUCT_PATH_RE):
        for match in pattern.finditer(html_text):
            canonical = _canonical_product_url(match.group("path"), base_url=catalog_url)
            if canonical:
                start = max(0, match.start() - 180)
                end = min(len(html_text), match.end() + 180)
                context = _compact(re.sub(r"<[^>]+>", " ", html_text[start:end]))
                contexts.setdefault(canonical, []).append(context)

    scope = _scope_for_catalog(catalog_url)
    results: list[CatalogLink] = []
    for url, raw_contexts in contexts.items():
        context = _compact(" ".join(raw_contexts))[:1000]
        clothing = tuple(sorted(set(_matched_terms(context, _CLOTHING_TERMS))))
        commercial = tuple(
            sorted(
                set(_matched_terms(context, _COMMERCIAL_TERMS))
                | set(_matched_terms(context, _SOURCE_COMMERCIAL_TERMS))
            )
        )
        rank = 90 if scope == "PALLET_AUCTIONS" else 60
        rank += min(30, len(clothing) * 10)
        rank += min(20, len(commercial) * 5)
        rank += 3 if context else 0
        results.append(
            CatalogLink(
                url=url,
                catalog_url=catalog_url,
                catalog_scope=scope,
                context=context,
                clothing_terms=clothing,
                commercial_terms=commercial,
                discovery_rank=rank,
            )
        )
    return sorted(results, key=lambda item: (-item.discovery_rank, item.url))


class _ProductParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.ignore_depth = 0
        self.h1_depth = 0
        self.json_ld_depth = 0
        self.visible: list[str] = []
        self.heading: list[str] = []
        self.meta: list[str] = []
        self.json_ld: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._active_href: str | None = None
        self._active_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        values = {key.casefold(): value or "" for key, value in attrs}
        folded = tag.casefold()
        if folded in {"style", "noscript", "svg", "template"}:
            self.ignore_depth += 1
        elif folded == "script":
            if values.get("type", "").casefold() == "application/ld+json":
                self.json_ld_depth += 1
            else:
                self.ignore_depth += 1
        elif folded == "h1":
            self.h1_depth += 1
        elif folded == "meta" and values.get("content"):
            self.meta.append(_compact(values["content"]))
        elif folded == "a":
            self._active_href = values.get("href") or None
            self._active_parts = [values.get("title", ""), values.get("aria-label", "")]

    def handle_endtag(self, tag: str) -> None:
        folded = tag.casefold()
        if folded in {"style", "noscript", "svg", "template"} and self.ignore_depth:
            self.ignore_depth -= 1
        elif folded == "script":
            if self.json_ld_depth:
                self.json_ld_depth -= 1
            elif self.ignore_depth:
                self.ignore_depth -= 1
        elif folded == "h1" and self.h1_depth:
            self.h1_depth -= 1
        elif folded == "a" and self._active_href:
            self.links.append(
                (self._active_href, _compact(" ".join(self._active_parts)))
            )
            self._active_href = None
            self._active_parts = []

    def handle_data(self, data: str) -> None:
        value = _compact(data)
        if not value:
            return
        if self.json_ld_depth:
            self.json_ld.append(value)
            return
        if self.ignore_depth:
            return
        self.visible.append(value)
        if self.h1_depth:
            self.heading.append(value)
        if self._active_href:
            self._active_parts.append(value)


def _product_document(
    *,
    html_text: str,
    source_url: str,
) -> tuple[str, str, list[str], str]:
    parser = _ProductParser(source_url)
    parser.feed(html_text)
    title = _compact(" ".join(parser.heading) or " ".join(parser.meta[:2]))[:1000]
    text = _compact(" ".join([*parser.meta, *parser.visible, *parser.json_ld]))[:250_000]
    packing_urls: list[str] = []
    for raw_url, context in parser.links:
        absolute = urljoin(source_url, raw_url)
        folded = f"{raw_url} {context}".casefold()
        if any(term in folded for term in _PACKING_TERMS) or re.search(r"\.(?:csv|xlsx?|pdf)(?:$|[?#])", raw_url, re.IGNORECASE):
            packing_urls.append(absolute)
    return (
        title,
        text,
        list(dict.fromkeys(packing_urls))[:10],
        sha256(html_text.encode("utf-8")).hexdigest(),
    )


def stockhurt_candidate_from_product_html(
    *,
    source_url: str,
    html_text: str,
    observed_at: datetime,
    catalog_link: CatalogLink | None = None,
) -> dict[str, Any] | None:
    canonical_url = _canonical_product_url(source_url, base_url="https://stockhurt.com/")
    if not canonical_url or is_source_protection_challenge(html_text):
        return None
    title, text, packing_urls, page_hash = _product_document(
        html_text=html_text,
        source_url=canonical_url,
    )
    combined = _compact(f"{title} {text}")
    clothing_terms = _matched_terms(combined, _CLOTHING_TERMS)
    commercial_terms = sorted(
        set(_matched_terms(combined, _COMMERCIAL_TERMS))
        | set(_matched_terms(combined, _SOURCE_COMMERCIAL_TERMS))
    )
    if not clothing_terms or not commercial_terms:
        return None

    minimum_order, minimum_order_unit, minimum_span = _extract_minimum_order(combined)
    quantity, quantity_unit = _extract_inventory_quantity(
        combined,
        moq_span=minimum_span,
    )
    price_text, price, currency, price_basis = _extract_price(combined)
    current_bid_match = _CURRENT_BID_RE.search(combined)
    current_bid = _parse_number(current_bid_match.group("amount")) if current_bid_match else None
    if current_bid_match:
        currency = _currency(
            current_bid_match.group("symbol"),
            current_bid_match.group("code"),
        ) or currency
    weight_match = _WEIGHT_RE.search(combined)
    weight_kg = _parse_number(weight_match.group("amount")) if weight_match else None
    if weight_kg is not None and weight_match and not weight_match.group("unit").casefold().startswith("kg"):
        weight_kg = round(weight_kg * 0.45359237, 3)

    grade = _extract_grade(combined)
    brands = _extract_source_brands(combined)
    condition_terms = _matched_terms(combined, _CONDITION_TERMS)
    manifest_terms = _matched_terms(combined, _MANIFEST_TERMS)
    shipping_terms = _matched_terms(combined, _SHIPPING_TERMS)
    authenticity_terms = _matched_terms(combined, _AUTHENTICITY_TERMS)
    auction_terms = _matched_terms(combined, _AUCTION_TERMS)
    out_of_stock_terms = _matched_terms(combined, _OUT_OF_STOCK_TERMS)
    is_auction = bool(auction_terms) or bool(
        catalog_link and catalog_link.catalog_scope == "PALLET_AUCTIONS"
    )
    listing_status = "OUT_OF_STOCK" if out_of_stock_terms else "ACTIVE_REQUIRES_VERIFICATION"
    sku_match = _SKU_RE.search(combined)
    end_match = _AUCTION_END_RE.search(combined)
    auction_end_text = _compact(end_match.group("value")) if end_match else None
    manifest_available = bool(packing_urls or manifest_terms)
    stock_location = _extract_location(combined) or "Poland"

    missing_information: list[str] = []
    if quantity is None:
        missing_information.append("TOTAL_AVAILABLE_QUANTITY")
    if minimum_order is None:
        missing_information.append("MINIMUM_ORDER")
    if price is None and current_bid is None:
        missing_information.append("VISIBLE_PRICE_OR_BID")
    if not manifest_available:
        missing_information.append("MANIFEST_OR_PACKING_LIST")
    if brands and not authenticity_terms:
        missing_information.append("BRAND_AUTHENTICITY_EVIDENCE")
    if not shipping_terms:
        missing_information.append("SHIPPING_TO_NORWAY")
    if is_auction and not auction_end_text:
        missing_information.append("AUCTION_END_TIME")

    active_specific = listing_status != "OUT_OF_STOCK"
    opportunity_state = (
        "B2B_LEAD_REQUIRES_VERIFICATION"
        if active_specific and len(missing_information) <= 4
        else "EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION"
    )
    score = 50
    score += 10 if quantity is not None else 0
    score += 8 if minimum_order is not None else 0
    score += 10 if price is not None or current_bid is not None else 0
    score += 8 if manifest_available else 0
    score += 5 if grade or condition_terms else 0
    score += 5 if brands else 0
    score += 4 if shipping_terms else 0
    score -= 12 if listing_status == "OUT_OF_STOCK" else 0
    score = max(0, min(100, score))

    source_reference = (
        sku_match.group("value")
        if sku_match
        else urlsplit(canonical_url).path.rstrip("/").rsplit("/", 1)[-1]
    )
    evidence = [
        {
            "field": "official_product_page",
            "source_url": canonical_url,
            "page_sha256": page_hash,
        }
    ]
    if catalog_link:
        evidence.append(
            {
                "field": "official_catalog_discovery",
                "source_url": catalog_link.catalog_url,
                "catalog_scope": catalog_link.catalog_scope,
                "link_context": catalog_link.context,
            }
        )
    return {
        "candidate_id": "stockhurt-page:" + sha256(canonical_url.encode("utf-8")).hexdigest()[:24],
        "feed_family": FEED_FAMILY,
        "source_name": SOURCE_NAME,
        "source_country": SOURCE_COUNTRY,
        "official_domain": "stockhurt.com",
        "source_url": canonical_url,
        "source_reference": source_reference,
        "title": title or source_reference,
        "description": combined[:1500],
        "observed_at": _iso_utc(observed_at),
        "page_role": "PALLET_AUCTION_OFFER" if is_auction else "SPECIFIC_STOCK_OFFER",
        "listing_status": listing_status,
        "sale_mode": "AUCTION" if is_auction else "FIXED_PRICE_OR_ENQUIRY",
        "inventory_focus": "CLOTHING_FOOTWEAR_OR_ACCESSORIES_WHOLESALE",
        "clothing_terms": clothing_terms,
        "commercial_terms": commercial_terms,
        "auction_terms": auction_terms,
        "quantity": quantity,
        "quantity_unit": quantity_unit,
        "lot_size_band": _lot_size_band(quantity, quantity_unit),
        "minimum_order": minimum_order,
        "minimum_order_unit": minimum_order_unit,
        "unit_hint": _extract_unit_hint(combined),
        "price_text": price_text,
        "unit_price": price if price_basis == "PER_UNIT" else None,
        "total_price": price if price_basis != "PER_UNIT" else None,
        "current_bid": current_bid,
        "price_basis": price_basis,
        "currency": currency,
        "weight_kg": weight_kg,
        "grade": grade,
        "condition_terms": condition_terms,
        "brands": brands,
        "stock_location": stock_location,
        "auction_end_text": auction_end_text,
        "manifest_available": manifest_available,
        "manifest_urls": packing_urls,
        "manifest_terms": manifest_terms,
        "authenticity_evidence_visible": bool(authenticity_terms),
        "shipping_information_present": bool(shipping_terms),
        "seller_name": SOURCE_NAME,
        "seller_identity_status": "OFFICIAL_SOURCE_BRAND_REQUIRES_LEGAL_VERIFICATION",
        "missing_information": missing_information,
        "opportunity_state": opportunity_state,
        "verification_status": "OFFICIAL_PRODUCT_PAGE_TEXT_EXTRACTED_REQUIRES_HUMAN_REVIEW",
        "b2b_relevance_score": score,
        "discovery_method": "DIRECT_OFFICIAL_CATALOG",
        "discovered_from_catalog_url": catalog_link.catalog_url if catalog_link else None,
        "catalog_scope": catalog_link.catalog_scope if catalog_link else None,
        "catalog_discovery_rank": catalog_link.discovery_rank if catalog_link else None,
        "catalog_link_context": catalog_link.context if catalog_link else None,
        "page_sha256": page_hash,
        "source_evidence": evidence,
        "decision_owner": "HUMAN_OPERATOR",
        "quantity_size_rejection_applied": False,
        "recommended_operator_action": "REVIEW_PAGE_PACKING_LIST_PRICE_GRADE_SHIPPING_AND_DECIDE_MANUALLY",
        **_safety_payload(),
    }


def _robots_rules(text: str) -> tuple[list[tuple[str, str]], float]:
    delay_match = _DELAY_RE.search(text)
    delay = float(delay_match.group(1)) if delay_match else 1.0
    active = False
    rules: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        folded = key.casefold()
        if folded == "user-agent":
            active = value == "*"
        elif active and folded in {"allow", "disallow"} and value:
            rules.append((folded, value.rstrip("*")))
    return rules, delay


def _robots_allows(rules: list[tuple[str, str]], path: str) -> bool:
    matches = [(kind, value) for kind, value in rules if path.startswith(value)]
    return not matches or max(matches, key=lambda item: len(item[1]))[0] == "allow"


def collect_stockhurt_official_catalog_enrichment(
    *,
    observed_at: datetime | None = None,
    environment: Mapping[str, str] | None = None,
    page_fetcher: Callable[[str], FetchedPage] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    max_catalog_pages: int = DEFAULT_MAX_CATALOG_PAGES,
    max_product_pages: int = DEFAULT_MAX_PRODUCT_PAGES,
) -> dict[str, Any]:
    del environment  # Interface compatibility; direct official lane needs no API key.
    if not 1 <= max_catalog_pages <= MAX_CATALOG_PAGES:
        raise ValueError("max_catalog_pages exceeds bounded production scope")
    if not 1 <= max_product_pages <= MAX_PRODUCT_PAGES:
        raise ValueError("max_product_pages exceeds bounded production scope")
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    fetch = page_fetcher or StockhurtCatalogFetcher()
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso_utc(now),
        "feed_family": FEED_FAMILY,
        "purpose": "DIRECT_OFFICIAL_STOCKHURT_CATALOG_TO_PRODUCT_PAGE_DECISION_SUPPORT",
        "approved_official_domains": list(APPROVED_DOMAINS),
        "catalog_urls": list(CATALOG_URLS[:max_catalog_pages]),
        "catalog_page_limit": max_catalog_pages,
        "product_page_limit": max_product_pages,
        "robots_requests_made": 0,
        "catalog_requests_made": 0,
        "product_requests_made": 0,
        "requests_made": 0,
        "source_protection_challenge_count": 0,
        "discovered_product_url_count": 0,
        "selected_product_url_count": 0,
        "rejected_non_clothing_product_count": 0,
        "catalog_links": [],
        "candidate_count": 0,
        "candidates": [],
        "errors": [],
        "search_provider_used": False,
        "api_key_required": False,
        "incomplete_signals_preserved": True,
        "out_of_stock_signals_preserved": True,
        "quantity_size_rejection_enabled": False,
        "human_decision_required": True,
        "decision_owner": "HUMAN_OPERATOR",
        "not_part_of_opportunity_top5": True,
        **_safety_payload(),
    }
    try:
        robots_page = fetch(ROBOTS_URL)
        report["robots_requests_made"] = 1
        if is_source_protection_challenge(robots_page.text):
            report.update(
                requests_made=1,
                source_protection_challenge_count=1,
                status_counts={"BLOCKED_SOURCE_PROTECTION": 1},
                block_reason="SOURCE_PROTECTION_CHALLENGE_ON_ROBOTS",
            )
            return report
        rules, delay = _robots_rules(robots_page.text)
        report["crawl_delay_seconds"] = delay
        required_paths = ("/en/shop/", "/en/licytacje/", "/en/product/")
        if not all(_robots_allows(rules, path) for path in required_paths):
            report.update(
                requests_made=1,
                status_counts={"BLOCKED_ROBOTS": 1},
                block_reason="ROBOTS_DISALLOWS_CATALOG_OR_PRODUCT_PAGES",
            )
            return report
        if delay < 0 or delay > MAX_CRAWL_DELAY_SECONDS:
            report.update(
                requests_made=1,
                status_counts={"BLOCKED_ROBOTS": 1},
                block_reason="ROBOTS_CRAWL_DELAY_OUTSIDE_SAFE_RANGE",
            )
            return report

        deduplicated: dict[str, CatalogLink] = {}
        challenged_catalogs = 0
        for catalog_url in CATALOG_URLS[:max_catalog_pages]:
            sleep_fn(delay)
            page = fetch(catalog_url)
            report["catalog_requests_made"] += 1
            if is_source_protection_challenge(page.text):
                challenged_catalogs += 1
                report["source_protection_challenge_count"] += 1
                continue
            for link in discover_stockhurt_product_links(
                catalog_url=catalog_url,
                html_text=page.text,
            ):
                previous = deduplicated.get(link.url)
                if previous is None or link.discovery_rank > previous.discovery_rank:
                    deduplicated[link.url] = link

        ranked = sorted(
            deduplicated.values(),
            key=lambda item: (-item.discovery_rank, item.url),
        )
        report["discovered_product_url_count"] = len(ranked)
        report["catalog_links"] = [item.to_dict() for item in ranked[:50]]
        selected = ranked[:max_product_pages]
        report["selected_product_url_count"] = len(selected)

        candidates: list[dict[str, Any]] = []
        for link in selected:
            sleep_fn(delay)
            page = fetch(link.url)
            report["product_requests_made"] += 1
            if is_source_protection_challenge(page.text):
                report["source_protection_challenge_count"] += 1
                continue
            candidate = stockhurt_candidate_from_product_html(
                source_url=page.final_url,
                html_text=page.text,
                observed_at=now,
                catalog_link=link,
            )
            if candidate is None:
                report["rejected_non_clothing_product_count"] += 1
                continue
            candidate.update(
                page_http_status=page.status_code,
                page_content_type=page.content_type,
                page_bytes_read=page.bytes_read,
            )
            candidates.append(candidate)

        report["candidate_count"] = len(candidates)
        report["candidates"] = candidates
        report["requests_made"] = (
            report["robots_requests_made"]
            + report["catalog_requests_made"]
            + report["product_requests_made"]
        )
        if candidates:
            status = "SUCCESS"
            block_reason = None
        elif report["source_protection_challenge_count"] and (
            challenged_catalogs == report["catalog_requests_made"]
            or report["product_requests_made"] > 0
        ):
            status = "BLOCKED_SOURCE_PROTECTION"
            block_reason = "SOURCE_PROTECTION_CHALLENGE_PREVENTED_PRODUCT_ENRICHMENT"
        else:
            status = "VALID_ZERO"
            block_reason = None
        report["status_counts"] = {status: 1}
        report["block_reason"] = block_reason
        return report
    except Exception as exc:
        report["requests_made"] = (
            report["robots_requests_made"]
            + report["catalog_requests_made"]
            + report["product_requests_made"]
        )
        report["errors"].append(f"{type(exc).__name__}: {_compact(exc)[:300]}")
        report["status_counts"] = {"BLOCKED_RETRIEVAL": 1}
        report["block_reason"] = "OFFICIAL_CATALOG_OR_PRODUCT_RETRIEVAL_FAILED"
        return report
