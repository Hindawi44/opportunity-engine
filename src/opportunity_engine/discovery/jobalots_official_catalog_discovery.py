"""Discover Jobalots product links from official catalog pages and enrich them.

This lane does not depend on a search-engine result. It reads only robots.txt,
two fixed public catalog pages, and at most three official product pages. Product
pages are normalized by the established Jobalots official-page enrichment path.
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
from opportunity_engine.discovery.jobalots_clothing_auction_feed import (
    _SOURCE_CLOTHING_TERMS,
    _SOURCE_COMMERCIAL_TERMS,
)
from opportunity_engine.discovery.jobalots_official_page_enrichment import (
    FetchedPage,
    MAX_CRAWL_DELAY_SECONDS,
    MAX_RESPONSE_BYTES,
    ROBOTS_URL,
    jobalots_page_candidate_from_html,
)
from opportunity_engine.discovery.merkandi_b2b_liquidation_feed import (
    _CLOTHING_TERMS,
    _COMMERCIAL_TERMS,
    _matched_terms,
    _safety_payload,
)

SCHEMA_VERSION = "jobalots-official-catalog-discovery-1.0"
FEED_FAMILY = "JOBALOTS_OFFICIAL_CATALOG_DISCOVERY_V1"
SOURCE_NAME = "Jobalots"
APPROVED_DOMAINS = ("jobalots.com",)
APPROVED_HOSTS = ("jobalots.com", "www.jobalots.com")
CLOTHING_CATALOG_URL = (
    "https://jobalots.com/en/pages/products-on-auction"
    "?categories=clothing&currency=gbp&page=1"
)
ALL_CATALOG_URL = (
    "https://jobalots.com/en/pages/products-on-auction"
    "?currency=gbp&page=1"
)
CATALOG_URLS = (CLOTHING_CATALOG_URL, ALL_CATALOG_URL)
DEFAULT_MAX_CATALOG_PAGES = 2
MAX_CATALOG_PAGES = 2
DEFAULT_MAX_PRODUCT_PAGES = 3
MAX_PRODUCT_PAGES = 3
_DELAY_RE = re.compile(r"(?im)^\s*Crawl-delay\s*:\s*([\d.]+)\s*$")
_PRODUCT_PATH_RE = re.compile(
    r"(?:https?://(?:www\.)?jobalots\.com)?"
    r"(?P<path>/en/products/[A-Za-z0-9._~!$&'()*+,;=:@%-]+)",
    re.IGNORECASE,
)
_ESCAPED_PRODUCT_PATH_RE = re.compile(
    r"(?P<path>\\?/en\\?/products\\?/[A-Za-z0-9._~!$&'()*+,;=:@%-]+)",
    re.IGNORECASE,
)


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


class JobalotsCatalogFetcher:
    """HTTP fetcher restricted to robots, fixed catalogs, and product pages."""

    def __init__(self, timeout_seconds: float = 20.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = timeout_seconds

    def __call__(self, url: str) -> FetchedPage:
        if not _approved_fetch_url(url):
            raise ValueError("URL outside approved Jobalots catalog scope")
        request = Request(
            url,
            headers={
                "User-Agent": "OpportunityEngine/Jobalots-Catalog-Discovery-1.0",
                "Accept": (
                    "text/plain,*/*;q=0.1"
                    if url == ROBOTS_URL
                    else "text/html,application/xhtml+xml"
                ),
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise RuntimeError("response exceeded maximum byte limit")
            final_url = response.geturl() or url
            if not _approved_fetch_url(final_url, allow_query_variants=True):
                raise RuntimeError("redirect left approved Jobalots scope")
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
        or not path.casefold().startswith("/en/products/")
        or path.casefold() == "/en/products"
    ):
        return None
    return f"https://jobalots.com{path}"


def _approved_fetch_url(url: str, *, allow_query_variants: bool = False) -> bool:
    if url == ROBOTS_URL:
        return True
    if url in CATALOG_URLS:
        return True
    product = _canonical_product_url(url, base_url="https://jobalots.com/")
    if product:
        return True
    if not allow_query_variants:
        return False
    parts = urlsplit(url)
    host = (parts.hostname or "").casefold().rstrip(".")
    path = parts.path.rstrip("/").casefold()
    return (
        parts.scheme == "https"
        and host in APPROVED_HOSTS
        and path == "/en/pages/products-on-auction"
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
        if tag.casefold() == "a":
            self._active_href = values.get("href") or None
            self._active_parts = [
                values.get("title", ""),
                values.get("aria-label", ""),
                values.get("data-product-title", ""),
            ]
        elif tag.casefold() == "img" and self._active_href:
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
    return "CLOTHING_CATEGORY" if "categories=clothing" in catalog_url else "ALL_AUCTIONS"


def discover_product_links_from_catalog_html(
    *,
    catalog_url: str,
    html_text: str,
) -> list[CatalogLink]:
    if catalog_url not in CATALOG_URLS:
        raise ValueError("catalog_url is outside fixed production scope")
    parser = _CatalogParser(catalog_url)
    parser.feed(html_text)
    contexts: dict[str, list[str]] = {}
    for raw_url, context in parser.links:
        canonical = _canonical_product_url(raw_url, base_url=catalog_url)
        if canonical:
            contexts.setdefault(canonical, []).append(context)

    for match in _PRODUCT_PATH_RE.finditer(html_text):
        canonical = _canonical_product_url(match.group("path"), base_url=catalog_url)
        if canonical:
            start = max(0, match.start() - 180)
            end = min(len(html_text), match.end() + 180)
            contexts.setdefault(canonical, []).append(
                _compact(re.sub(r"<[^>]+>", " ", html_text[start:end]))
            )
    for match in _ESCAPED_PRODUCT_PATH_RE.finditer(html_text):
        canonical = _canonical_product_url(match.group("path"), base_url=catalog_url)
        if canonical:
            contexts.setdefault(canonical, []).append("")

    scope = _scope_for_catalog(catalog_url)
    discovered: list[CatalogLink] = []
    for url, raw_contexts in contexts.items():
        context = _compact(" ".join(raw_contexts))[:1000]
        clothing = tuple(
            sorted(
                set(_matched_terms(context, _CLOTHING_TERMS))
                | set(_matched_terms(context, _SOURCE_CLOTHING_TERMS))
            )
        )
        commercial = tuple(
            sorted(
                set(_matched_terms(context, _COMMERCIAL_TERMS))
                | set(_matched_terms(context, _SOURCE_COMMERCIAL_TERMS))
            )
        )
        rank = 100 if scope == "CLOTHING_CATEGORY" else 0
        rank += min(30, len(clothing) * 10)
        rank += min(15, len(commercial) * 5)
        rank += 3 if context else 0
        discovered.append(
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
    return sorted(discovered, key=lambda item: (-item.discovery_rank, item.url))


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


def collect_jobalots_official_catalog_discovery(
    *,
    observed_at: datetime | None = None,
    environment: Mapping[str, str] | None = None,
    page_fetcher: Callable[[str], FetchedPage] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    max_catalog_pages: int = DEFAULT_MAX_CATALOG_PAGES,
    max_product_pages: int = DEFAULT_MAX_PRODUCT_PAGES,
) -> dict[str, Any]:
    del environment  # Interface compatibility; this direct lane needs no API key.
    if not 1 <= max_catalog_pages <= MAX_CATALOG_PAGES:
        raise ValueError("max_catalog_pages exceeds bounded production scope")
    if not 1 <= max_product_pages <= MAX_PRODUCT_PAGES:
        raise ValueError("max_product_pages exceeds bounded production scope")
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    fetch = page_fetcher or JobalotsCatalogFetcher()
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso_utc(now),
        "feed_family": FEED_FAMILY,
        "purpose": "DIRECT_OFFICIAL_JOBALOTS_CATALOG_TO_PRODUCT_PAGE_DECISION_SUPPORT",
        "approved_official_domains": list(APPROVED_DOMAINS),
        "catalog_urls": list(CATALOG_URLS[:max_catalog_pages]),
        "catalog_page_limit": max_catalog_pages,
        "product_page_limit": max_product_pages,
        "robots_requests_made": 0,
        "catalog_requests_made": 0,
        "product_requests_made": 0,
        "requests_made": 0,
        "discovered_product_url_count": 0,
        "selected_product_url_count": 0,
        "catalog_links": [],
        "candidate_count": 0,
        "candidates": [],
        "errors": [],
        "search_provider_used": False,
        "api_key_required": False,
        "quantity_size_rejection_enabled": False,
        "human_decision_required": True,
        "decision_owner": "HUMAN_OPERATOR",
        "not_part_of_opportunity_top5": True,
        **_safety_payload(),
    }
    try:
        robots_page = fetch(ROBOTS_URL)
        report["robots_requests_made"] = 1
        rules, delay = _robots_rules(robots_page.text)
        report["crawl_delay_seconds"] = delay
        required_paths = (
            "/en/pages/products-on-auction",
            "/en/products/",
        )
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
        for catalog_url in CATALOG_URLS[:max_catalog_pages]:
            sleep_fn(delay)
            page = fetch(catalog_url)
            report["catalog_requests_made"] += 1
            for link in discover_product_links_from_catalog_html(
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
        rejected_non_clothing = 0
        for link in selected:
            sleep_fn(delay)
            page = fetch(link.url)
            report["product_requests_made"] += 1
            candidate = jobalots_page_candidate_from_html(
                source_url=page.final_url,
                html_text=page.text,
                observed_at=now,
            )
            if not candidate:
                rejected_non_clothing += 1
                continue
            candidate.update(
                feed_family=FEED_FAMILY,
                discovery_method="OFFICIAL_CATALOG_HTML",
                discovered_from_catalog_url=link.catalog_url,
                catalog_scope=link.catalog_scope,
                catalog_link_context=link.context,
                catalog_discovery_rank=link.discovery_rank,
                page_http_status=page.status_code,
                page_content_type=page.content_type,
                page_bytes_read=page.bytes_read,
            )
            candidates.append(candidate)

        report.update(
            candidate_count=len(candidates),
            candidates=candidates,
            rejected_non_clothing_product_count=rejected_non_clothing,
            requests_made=(
                report["robots_requests_made"]
                + report["catalog_requests_made"]
                + report["product_requests_made"]
            ),
            status_counts={"SUCCESS" if candidates else "VALID_ZERO": 1},
            block_reason=None,
        )
        return report
    except Exception as exc:
        report["errors"].append(f"{type(exc).__name__}: {_compact(exc)[:300]}")
        report.update(
            requests_made=(
                report["robots_requests_made"]
                + report["catalog_requests_made"]
                + report["product_requests_made"]
            ),
            status_counts={"BLOCKED_RETRIEVAL": 1},
            block_reason="OFFICIAL_CATALOG_OR_PRODUCT_RETRIEVAL_FAILED",
        )
        return report
