"""Bounded child-link resolution for verified aggregate clothing-stock pages.

Search providers may legitimately surface an aggregate stock page instead of a
single commercial lot. Such a page must never receive item-specific Tool
Learning credit, but it can be used as a read-only navigation parent when the
existing symmetric verifier has already proven all of the following:

* the original page was fetched successfully;
* the page is inside CLOTHING_INVENTORY;
* inventory and direct-sale evidence are present;
* the URL is not item-specific; and
* the page was therefore filtered from Tool Learning usefulness.

This layer re-fetches only those bounded parents, extracts same-origin descendant
links whose URL shape is item-specific, fetches those child pages, and accepts a
child only when the existing strict classifier returns EXACT_LOT_CANDIDATE. It
cannot contact sellers, bid, reserve, buy, pay, activate a provider, or mutate
production state.
"""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import urldefrag, urljoin, urlsplit

import requests

from opportunity_engine.discovery.exa_shadow_page_verification import (
    ACTIVE_STOCK_SIGNAL,
    EXACT_LOT_CANDIDATE,
    FETCH_FAILED,
    PageFetcher,
    _classify_page,
    _looks_item_specific_url,
    fetch_public_page,
)
from opportunity_engine.discovery.keyword_shadow_verification import _public_https_url
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY

SCHEMA_VERSION = "exact-lot-child-link-resolution-1.0"
LAB_FAMILY = "EXACT_LOT_CHILD_LINK_RESOLUTION_V1"
SUPPORTED_PROVIDERS = frozenset({"exa", "brave"})
MAX_PARENT_FETCHES = 12
MAX_CHILD_LINKS_PER_PARENT = 20
MAX_CHILD_PAGE_FETCHES = 30
MAX_RESPONSE_BYTES = 800_000


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


@dataclass(frozen=True, slots=True)
class AggregateHtmlFetchResult:
    requested_url: str
    final_url: str
    ok: bool
    status_code: int | None
    html: str
    error: str | None = None
    truncated: bool = False


AggregateHtmlFetcher = Callable[[str], AggregateHtmlFetchResult]


def fetch_public_html(url: str) -> AggregateHtmlFetchResult:
    """Fetch one bounded public HTTPS HTML page for link extraction only."""
    requested = _compact(url)
    if not _public_https_url(requested):
        return AggregateHtmlFetchResult(
            requested_url=requested,
            final_url=requested,
            ok=False,
            status_code=None,
            html="",
            error="UNSAFE_OR_UNSUPPORTED_URL",
        )
    try:
        with requests.get(
            requested,
            timeout=(5, 12),
            allow_redirects=True,
            stream=True,
            headers={
                "User-Agent": "opportunity-engine-exact-lot-child-link-resolver/1.0",
                "Accept": "text/html,application/xhtml+xml",
            },
        ) as response:
            final_url = str(response.url or requested)
            if not _public_https_url(final_url):
                return AggregateHtmlFetchResult(
                    requested_url=requested,
                    final_url=final_url,
                    ok=False,
                    status_code=response.status_code,
                    html="",
                    error="UNSAFE_REDIRECT_TARGET",
                )
            if response.status_code < 200 or response.status_code >= 300:
                return AggregateHtmlFetchResult(
                    requested_url=requested,
                    final_url=final_url,
                    ok=False,
                    status_code=response.status_code,
                    html="",
                    error=f"HTTP_{response.status_code}",
                )
            content_type = str(response.headers.get("Content-Type") or "").casefold()
            if "html" not in content_type:
                return AggregateHtmlFetchResult(
                    requested_url=requested,
                    final_url=final_url,
                    ok=False,
                    status_code=response.status_code,
                    html="",
                    error="NON_HTML_CONTENT",
                )

            chunks: list[bytes] = []
            total = 0
            truncated = False
            for chunk in response.iter_content(chunk_size=16_384):
                if not chunk:
                    continue
                remaining = MAX_RESPONSE_BYTES - total
                if remaining <= 0:
                    truncated = True
                    break
                if len(chunk) > remaining:
                    chunks.append(chunk[:remaining])
                    total += remaining
                    truncated = True
                    break
                chunks.append(chunk)
                total += len(chunk)
            body = b"".join(chunks)
            encoding = response.encoding or "utf-8"
            try:
                html = body.decode(encoding, errors="replace")
            except LookupError:
                html = body.decode("utf-8", errors="replace")
            if not html.strip():
                return AggregateHtmlFetchResult(
                    requested_url=requested,
                    final_url=final_url,
                    ok=False,
                    status_code=response.status_code,
                    html="",
                    error="EMPTY_HTML",
                    truncated=truncated,
                )
            return AggregateHtmlFetchResult(
                requested_url=requested,
                final_url=final_url,
                ok=True,
                status_code=response.status_code,
                html=html,
                error=None,
                truncated=truncated,
            )
    except requests.RequestException as exc:
        return AggregateHtmlFetchResult(
            requested_url=requested,
            final_url=requested,
            ok=False,
            status_code=None,
            html="",
            error=f"{type(exc).__name__}: {str(exc)[:200]}",
        )


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a":
            return
        for key, value in attrs:
            if key.casefold() == "href" and value:
                self.hrefs.append(value.strip())
                break


def _extract_candidate_child_links(*, parent_url: str, html_text: str) -> list[str]:
    """Return conservative same-origin descendant item/detail URLs in document order."""
    parent = _compact(parent_url)
    if not _public_https_url(parent):
        return []
    try:
        parent_parts = urlsplit(parent)
    except ValueError:
        return []
    parent_host = (parent_parts.hostname or "").casefold()
    parent_path = parent_parts.path or "/"
    parent_prefix = parent_path.rstrip("/") + "/"

    parser = _AnchorParser()
    try:
        parser.feed(str(html_text or ""))
    except (ValueError, TypeError):
        return []

    output: list[str] = []
    seen: set[str] = set()
    parent_defragged = urldefrag(parent).url
    for href in parser.hrefs:
        try:
            candidate = urldefrag(urljoin(parent, href)).url
            parts = urlsplit(candidate)
        except ValueError:
            continue
        if parts.scheme.casefold() != "https":
            continue
        if (parts.hostname or "").casefold() != parent_host:
            continue
        if candidate == parent_defragged:
            continue
        if not (parts.path or "/").startswith(parent_prefix):
            continue
        if not _looks_item_specific_url(candidate):
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        output.append(candidate)
    return output


def _eligible_parent(page: dict[str, Any]) -> bool:
    evidence = page.get("evidence") or {}
    return bool(
        page.get("fetch_ok") is True
        and page.get("classification") == ACTIVE_STOCK_SIGNAL
        and page.get("tool_learning_useful") is not True
        and evidence.get("project_domain") == CLOTHING_INVENTORY
        and evidence.get("inventory_evidence") is True
        and evidence.get("direct_sale_evidence") is True
        and evidence.get("item_specific_url_evidence") is False
    )


def _base(*, provider: str, max_parent_fetches: int, max_child_page_fetches: int) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "lab_family": LAB_FAMILY,
        "provider": provider,
        "shadow_only": True,
        "required_project_domain": CLOTHING_INVENTORY,
        "project_domain_gate_enforced": True,
        "commercial_specificity_gate_enforced": True,
        "same_origin_child_links_only": True,
        "descendant_path_child_links_only": True,
        "exact_lot_acceptance_only": True,
        "max_parent_fetches": max_parent_fetches,
        "max_child_page_fetches": max_child_page_fetches,
        "production_provider_activation": False,
        "promotion_to_live_engine_enabled": False,
        "production_mutation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def resolve_exact_lot_child_links(
    provider_verification: dict[str, Any],
    *,
    aggregate_fetcher: AggregateHtmlFetcher = fetch_public_html,
    child_page_fetcher: PageFetcher = fetch_public_page,
    max_parent_fetches: int = 6,
    max_child_links_per_parent: int = 10,
    max_child_page_fetches: int = 20,
) -> dict[str, Any]:
    """Resolve exact-lot child pages from verified non-specific clothing-sale parents."""
    if not 1 <= max_parent_fetches <= MAX_PARENT_FETCHES:
        raise ValueError(f"max_parent_fetches must be between 1 and {MAX_PARENT_FETCHES}")
    if not 1 <= max_child_links_per_parent <= MAX_CHILD_LINKS_PER_PARENT:
        raise ValueError(
            f"max_child_links_per_parent must be between 1 and {MAX_CHILD_LINKS_PER_PARENT}"
        )
    if not 1 <= max_child_page_fetches <= MAX_CHILD_PAGE_FETCHES:
        raise ValueError(
            f"max_child_page_fetches must be between 1 and {MAX_CHILD_PAGE_FETCHES}"
        )

    provider = _compact(provider_verification.get("provider")).casefold()
    base = _base(
        provider=provider,
        max_parent_fetches=max_parent_fetches,
        max_child_page_fetches=max_child_page_fetches,
    )
    if provider_verification.get("status") != "SUCCESS":
        return {**base, "status": "BLOCKED_INPUT", "block_reason": "VERIFICATION_NOT_SUCCESSFUL", "exact_lots": [], "child_results": []}
    if provider not in SUPPORTED_PROVIDERS:
        return {**base, "status": "BLOCKED_INPUT", "block_reason": "UNSUPPORTED_PROVIDER", "exact_lots": [], "child_results": []}
    if provider_verification.get("shadow_only") is not True:
        return {**base, "status": "BLOCKED_INPUT", "block_reason": "INPUT_NOT_SHADOW_ONLY", "exact_lots": [], "child_results": []}
    if provider_verification.get("symmetric_provider_verification") is not True:
        return {**base, "status": "BLOCKED_INPUT", "block_reason": "INPUT_NOT_SYMMETRIC_PROVIDER_VERIFICATION", "exact_lots": [], "child_results": []}
    if provider_verification.get("commercial_specificity_gate_enforced") is not True:
        return {**base, "status": "BLOCKED_INPUT", "block_reason": "COMMERCIAL_SPECIFICITY_GATE_NOT_ENFORCED", "exact_lots": [], "child_results": []}
    if provider_verification.get("project_domain_gate_enforced") is not True or _compact(
        provider_verification.get("required_project_domain")
    ) != CLOTHING_INVENTORY:
        return {**base, "status": "BLOCKED_INPUT", "block_reason": "INPUT_NOT_CLOTHING_DOMAIN_GATED", "exact_lots": [], "child_results": []}

    eligible: list[dict[str, Any]] = []
    seen_parents: set[str] = set()
    for page in provider_verification.get("verified_pages") or []:
        if not isinstance(page, dict) or not _eligible_parent(page):
            continue
        parent_url = _compact(page.get("final_url") or page.get("url"))
        if not parent_url or parent_url in seen_parents:
            continue
        seen_parents.add(parent_url)
        eligible.append(page)

    parent_results: list[dict[str, Any]] = []
    child_candidates: list[dict[str, Any]] = []
    seen_children: set[str] = set()
    parent_attempted = 0
    parent_succeeded = 0

    for page in eligible:
        parent_url = _compact(page.get("final_url") or page.get("url"))
        if parent_attempted >= max_parent_fetches:
            parent_results.append(
                {
                    "parent_url": parent_url,
                    "fetch_ok": False,
                    "fetch_error": "PARENT_BUDGET_EXHAUSTED",
                    "child_url_count": 0,
                }
            )
            continue
        parent_attempted += 1
        fetched = aggregate_fetcher(parent_url)
        if not fetched.ok:
            parent_results.append(
                {
                    "parent_url": parent_url,
                    "fetch_ok": False,
                    "status_code": fetched.status_code,
                    "final_url": fetched.final_url,
                    "fetch_error": fetched.error,
                    "child_url_count": 0,
                }
            )
            continue
        parent_succeeded += 1
        resolved_parent = fetched.final_url or parent_url
        links = _extract_candidate_child_links(
            parent_url=resolved_parent,
            html_text=fetched.html,
        )[:max_child_links_per_parent]
        parent_results.append(
            {
                "parent_url": parent_url,
                "fetch_ok": True,
                "status_code": fetched.status_code,
                "final_url": resolved_parent,
                "fetch_error": None,
                "truncated": fetched.truncated,
                "child_url_count": len(links),
                "child_urls": links,
            }
        )
        for child_url in links:
            if child_url in seen_children:
                continue
            seen_children.add(child_url)
            child_candidates.append(
                {
                    "url": child_url,
                    "parent_url": resolved_parent,
                    "market_code": _compact(page.get("market_code")).upper(),
                    "query": _compact(page.get("query")),
                    "provider": provider,
                }
            )

    child_results: list[dict[str, Any]] = []
    exact_lots: list[dict[str, Any]] = []
    child_attempted = 0
    child_succeeded = 0
    child_budget_exhausted = 0

    for candidate in child_candidates:
        if child_attempted >= max_child_page_fetches:
            child_budget_exhausted += 1
            child_results.append(
                {
                    **candidate,
                    "classification": "NOT_FETCHED_BUDGET",
                    "fetch_ok": False,
                    "fetch_error": "CHILD_PAGE_BUDGET_EXHAUSTED",
                    "exact_lot_accepted": False,
                    "evidence": {},
                }
            )
            continue
        child_attempted += 1
        fetched = child_page_fetcher(candidate["url"])
        if not fetched.ok:
            child_results.append(
                {
                    **candidate,
                    "classification": FETCH_FAILED,
                    "fetch_ok": False,
                    "status_code": fetched.status_code,
                    "final_url": fetched.final_url,
                    "fetch_error": fetched.error,
                    "exact_lot_accepted": False,
                    "evidence": {},
                }
            )
            continue
        child_succeeded += 1
        classification, evidence = _classify_page(
            title=fetched.title,
            text=fetched.text,
            url=fetched.final_url or candidate["url"],
        )
        accepted = bool(
            classification == EXACT_LOT_CANDIDATE
            and evidence.get("project_domain") == CLOTHING_INVENTORY
            and evidence.get("item_specific_url_evidence") is True
            and evidence.get("inventory_evidence") is True
            and evidence.get("direct_sale_evidence") is True
            and evidence.get("price_evidence") is True
            and evidence.get("quantity_evidence") is True
        )
        row = {
            **candidate,
            "classification": classification,
            "fetch_ok": True,
            "status_code": fetched.status_code,
            "final_url": fetched.final_url,
            "fetch_error": None,
            "truncated": fetched.truncated,
            "exact_lot_accepted": accepted,
            "evidence": evidence,
        }
        child_results.append(row)
        if accepted:
            exact_lots.append(row)

    return {
        **base,
        "status": "SUCCESS",
        "block_reason": None,
        "eligible_parent_count": len(eligible),
        "parent_fetches_attempted": parent_attempted,
        "parent_fetches_succeeded": parent_succeeded,
        "parent_results": parent_results,
        "candidate_child_url_count": len(child_candidates),
        "child_page_fetches_attempted": child_attempted,
        "child_page_fetches_succeeded": child_succeeded,
        "child_budget_exhausted_count": child_budget_exhausted,
        "exact_lot_candidate_count": len(exact_lots),
        "child_results": child_results,
        "exact_lots": exact_lots,
        "interpretation_guard": (
            "Aggregate parents remain non-opportunities. Only directly fetched same-origin descendant child pages that prove clothing inventory, direct sale, item specificity, price and quantity are accepted as exact-lot evidence."
        ),
    }
