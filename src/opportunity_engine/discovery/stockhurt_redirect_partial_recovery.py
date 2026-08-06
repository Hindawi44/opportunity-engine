"""Install resilient redirect and partial-recovery behavior for Stock-Hurt.

The repository already uses small installation hooks for compatibility fixes. This
hook keeps the existing parser contract, but replaces the live fetch/collection
boundary so an official same-domain redirect or one protected catalogue cannot
cancel usable results from the other catalogue.
"""
from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from opportunity_engine.discovery import stockhurt_official_catalog_enrichment as target

PATCH_SCHEMA_VERSION = "stockhurt-official-catalog-enrichment-1.1"
_INSTALLED = False


def _official_https(url: str) -> bool:
    parts = urlsplit(url)
    return (
        parts.scheme == "https"
        and (parts.hostname or "").casefold().rstrip(".") in target.APPROVED_HOSTS
    )


def approved_stockhurt_redirect(requested_url: str, final_url: str) -> bool:
    """Validate the final URL according to the type of initial request."""
    if not _official_https(final_url):
        return False
    if requested_url == target.ROBOTS_URL:
        return urlsplit(final_url).path.rstrip("/").casefold() == "/robots.txt"
    if requested_url in target.CATALOG_URLS:
        # Live catalogue routing can change locale/canonical path. The final page
        # remains read-only and must stay on the official HTTPS domain.
        return True
    return target._canonical_product_url(final_url, base_url=requested_url) is not None


class ResilientStockhurtCatalogFetcher:
    """Official-domain fetcher that records and permits safe internal redirects."""

    def __init__(self, timeout_seconds: float = 20.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = timeout_seconds

    def __call__(self, url: str) -> target.FetchedPage:
        if not target._approved_fetch_url(url):
            raise ValueError("URL outside approved Stock-Hurt scope")
        request = Request(
            url,
            headers={
                "User-Agent": "OpportunityEngine/StockHurt-Catalog-Enrichment-1.1",
                "Accept": (
                    "text/plain,*/*;q=0.1"
                    if url == target.ROBOTS_URL
                    else "text/html,application/xhtml+xml"
                ),
                "Accept-Language": "en-GB,en;q=0.8",
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            body = response.read(target.MAX_RESPONSE_BYTES + 1)
            if len(body) > target.MAX_RESPONSE_BYTES:
                raise RuntimeError("response exceeded maximum byte limit")
            final_url = response.geturl() or url
            if not approved_stockhurt_redirect(url, final_url):
                raise RuntimeError(
                    f"redirect left approved Stock-Hurt scope: {url} -> {final_url}"
                )
            return target.FetchedPage(
                requested_url=url,
                final_url=final_url,
                status_code=int(getattr(response, "status", 200)),
                content_type=target._compact(response.headers.get("Content-Type")),
                text=body.decode("utf-8", errors="replace"),
                bytes_read=len(body),
            )


def _validate_page(requested_url: str, page: target.FetchedPage) -> None:
    if page.requested_url != requested_url:
        raise RuntimeError("fetcher returned mismatched requested_url")
    if not approved_stockhurt_redirect(requested_url, page.final_url):
        raise RuntimeError(
            f"redirect left approved Stock-Hurt scope: {requested_url} -> {page.final_url}"
        )


def _fetch_record(
    requested_url: str,
    page: target.FetchedPage | None,
    *,
    challenge: bool = False,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "requested_url": requested_url,
        "final_url": page.final_url if page else None,
        "redirected": bool(
            page and page.final_url.rstrip("/") != requested_url.rstrip("/")
        ),
        "http_status": page.status_code if page else None,
        "content_type": page.content_type if page else None,
        "source_protection_challenge": challenge,
        "error": error,
    }


def _base_report(now: datetime, max_catalog_pages: int, max_product_pages: int) -> dict[str, Any]:
    return {
        "schema_version": PATCH_SCHEMA_VERSION,
        "generated_at": target._iso_utc(now),
        "feed_family": target.FEED_FAMILY,
        "purpose": "DIRECT_OFFICIAL_STOCKHURT_CATALOG_TO_PRODUCT_PAGE_DECISION_SUPPORT",
        "approved_official_domains": list(target.APPROVED_DOMAINS),
        "catalog_urls": list(target.CATALOG_URLS[:max_catalog_pages]),
        "catalog_page_limit": max_catalog_pages,
        "product_page_limit": max_product_pages,
        "robots_requests_made": 0,
        "catalog_requests_made": 0,
        "product_requests_made": 0,
        "requests_made": 0,
        "catalog_success_count": 0,
        "catalog_error_count": 0,
        "product_error_count": 0,
        "catalog_redirect_count": 0,
        "product_redirect_count": 0,
        "source_protection_challenge_count": 0,
        "discovered_product_url_count": 0,
        "selected_product_url_count": 0,
        "rejected_non_clothing_product_count": 0,
        "catalog_fetches": [],
        "product_fetches": [],
        "catalog_links": [],
        "candidate_count": 0,
        "candidates": [],
        "errors": [],
        "search_provider_used": False,
        "api_key_required": False,
        "partial_results_preserved": True,
        "incomplete_signals_preserved": True,
        "out_of_stock_signals_preserved": True,
        "quantity_size_rejection_enabled": False,
        "human_decision_required": True,
        "decision_owner": "HUMAN_OPERATOR",
        "not_part_of_opportunity_top5": True,
        **target._safety_payload(),
    }


def _finalize_status(report: dict[str, Any]) -> None:
    candidates = report["candidate_count"] > 0
    challenge = report["source_protection_challenge_count"] > 0
    errors = report["catalog_error_count"] > 0 or report["product_error_count"] > 0
    if candidates:
        if challenge:
            status = "PARTIAL_SUCCESS_WITH_SOURCE_PROTECTION"
            reason = "SOURCE_PROTECTION_ON_SOME_PAGES_PARTIAL_RESULTS_PRESERVED"
        elif errors:
            status = "PARTIAL_SUCCESS_WITH_RETRIEVAL_ERRORS"
            reason = "SOME_PAGES_FAILED_PARTIAL_RESULTS_PRESERVED"
        else:
            status, reason = "SUCCESS", None
    elif report["catalog_success_count"] == 0:
        if challenge:
            status = "BLOCKED_SOURCE_PROTECTION"
            reason = "SOURCE_PROTECTION_PREVENTED_ALL_CATALOG_ENRICHMENT"
        elif errors:
            status = "BLOCKED_RETRIEVAL"
            reason = "CATALOG_RETRIEVAL_FAILED"
        else:
            status, reason = "VALID_ZERO", None
    elif challenge:
        status = "PARTIAL_VALID_ZERO_WITH_SOURCE_PROTECTION"
        reason = "ACCESSIBLE_CATALOGS_RETURNED_NO_CANDIDATES_OTHER_PAGES_PROTECTED"
    elif errors:
        status = "PARTIAL_VALID_ZERO_WITH_RETRIEVAL_ERRORS"
        reason = "ACCESSIBLE_CATALOGS_RETURNED_NO_CANDIDATES_OTHER_PAGES_FAILED"
    else:
        status, reason = "VALID_ZERO", None
    report["status_counts"] = {status: 1}
    report["block_reason"] = reason


def collect_stockhurt_redirect_partial_recovery(
    *,
    observed_at: datetime | None = None,
    environment: Mapping[str, str] | None = None,
    page_fetcher: Callable[[str], target.FetchedPage] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    max_catalog_pages: int = target.DEFAULT_MAX_CATALOG_PAGES,
    max_product_pages: int = target.DEFAULT_MAX_PRODUCT_PAGES,
) -> dict[str, Any]:
    del environment
    if not 1 <= max_catalog_pages <= target.MAX_CATALOG_PAGES:
        raise ValueError("max_catalog_pages exceeds bounded production scope")
    if not 1 <= max_product_pages <= target.MAX_PRODUCT_PAGES:
        raise ValueError("max_product_pages exceeds bounded production scope")
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    fetch = page_fetcher or ResilientStockhurtCatalogFetcher()
    report = _base_report(now, max_catalog_pages, max_product_pages)

    report["robots_requests_made"] = 1
    try:
        robots_page = fetch(target.ROBOTS_URL)
        _validate_page(target.ROBOTS_URL, robots_page)
    except Exception as exc:
        report["requests_made"] = 1
        report["errors"].append(f"{type(exc).__name__}: {target._compact(exc)[:300]}")
        report["status_counts"] = {"BLOCKED_RETRIEVAL": 1}
        report["block_reason"] = "ROBOTS_RETRIEVAL_FAILED"
        return report
    if target.is_source_protection_challenge(robots_page.text):
        report.update(
            requests_made=1,
            source_protection_challenge_count=1,
            status_counts={"BLOCKED_SOURCE_PROTECTION": 1},
            block_reason="SOURCE_PROTECTION_CHALLENGE_ON_ROBOTS",
        )
        return report
    rules, delay = target._robots_rules(robots_page.text)
    report["crawl_delay_seconds"] = delay
    required_paths = ("/en/shop/", "/en/licytacje/", "/en/product/")
    if not all(target._robots_allows(rules, path) for path in required_paths):
        report.update(
            requests_made=1,
            status_counts={"BLOCKED_ROBOTS": 1},
            block_reason="ROBOTS_DISALLOWS_CATALOG_OR_PRODUCT_PAGES",
        )
        return report
    if delay < 0 or delay > target.MAX_CRAWL_DELAY_SECONDS:
        report.update(
            requests_made=1,
            status_counts={"BLOCKED_ROBOTS": 1},
            block_reason="ROBOTS_CRAWL_DELAY_OUTSIDE_SAFE_RANGE",
        )
        return report

    deduplicated: dict[str, target.CatalogLink] = {}
    for catalog_url in target.CATALOG_URLS[:max_catalog_pages]:
        sleep_fn(delay)
        report["catalog_requests_made"] += 1
        try:
            page = fetch(catalog_url)
            _validate_page(catalog_url, page)
        except Exception as exc:
            message = f"{type(exc).__name__}: {target._compact(exc)[:300]}"
            report["catalog_error_count"] += 1
            report["errors"].append(f"{catalog_url}: {message}")
            report["catalog_fetches"].append(
                _fetch_record(catalog_url, None, error=message)
            )
            continue
        challenge = target.is_source_protection_challenge(page.text)
        record = _fetch_record(catalog_url, page, challenge=challenge)
        report["catalog_fetches"].append(record)
        report["catalog_redirect_count"] += int(record["redirected"])
        if challenge:
            report["source_protection_challenge_count"] += 1
            continue
        report["catalog_success_count"] += 1
        for link in target.discover_stockhurt_product_links(
            catalog_url=catalog_url,
            html_text=page.text,
        ):
            previous = deduplicated.get(link.url)
            if previous is None or link.discovery_rank > previous.discovery_rank:
                deduplicated[link.url] = link

    ranked = sorted(
        deduplicated.values(), key=lambda item: (-item.discovery_rank, item.url)
    )
    report["discovered_product_url_count"] = len(ranked)
    report["catalog_links"] = [item.to_dict() for item in ranked[:50]]
    selected = ranked[:max_product_pages]
    report["selected_product_url_count"] = len(selected)

    candidates: list[dict[str, Any]] = []
    for link in selected:
        sleep_fn(delay)
        report["product_requests_made"] += 1
        try:
            page = fetch(link.url)
            _validate_page(link.url, page)
        except Exception as exc:
            message = f"{type(exc).__name__}: {target._compact(exc)[:300]}"
            report["product_error_count"] += 1
            report["errors"].append(f"{link.url}: {message}")
            report["product_fetches"].append(
                _fetch_record(link.url, None, error=message)
            )
            continue
        challenge = target.is_source_protection_challenge(page.text)
        record = _fetch_record(link.url, page, challenge=challenge)
        report["product_fetches"].append(record)
        report["product_redirect_count"] += int(record["redirected"])
        if challenge:
            report["source_protection_challenge_count"] += 1
            continue
        candidate = target.stockhurt_candidate_from_product_html(
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
            requested_product_url=link.url,
            final_product_url=page.final_url,
        )
        candidates.append(candidate)

    report["candidate_count"] = len(candidates)
    report["candidates"] = candidates
    report["requests_made"] = (
        report["robots_requests_made"]
        + report["catalog_requests_made"]
        + report["product_requests_made"]
    )
    _finalize_status(report)
    return report


def install_stockhurt_redirect_partial_recovery() -> None:
    """Patch the established module before callers import its collector symbol."""
    global _INSTALLED
    if _INSTALLED:
        return
    target.SCHEMA_VERSION = PATCH_SCHEMA_VERSION
    target.StockhurtCatalogFetcher = ResilientStockhurtCatalogFetcher
    target.collect_stockhurt_official_catalog_enrichment = (
        collect_stockhurt_redirect_partial_recovery
    )
    _INSTALLED = True
