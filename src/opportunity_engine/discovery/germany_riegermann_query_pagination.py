"""Query-style pagination compatibility for the public Riegermann catalog.

Riegermann's friendly auction URL exposes catalog controls whose links use the
query-style ``/de/objekte?Accid=...`` endpoint.  The base compatibility layer
only accepts friendly ``/de/objekte/au-...`` URLs, so this module adds a bounded,
fail-closed bridge for the public query endpoint without broadening access to
login, bidding, purchasing, payment, or financial calculations.
"""
from __future__ import annotations

import hashlib
import html
import math
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, parse_qsl, urlencode, urljoin, urlparse, urlunparse

from opportunity_engine.discovery import germany_riegermann_live as live_layer
from opportunity_engine.discovery import germany_riegermann_live_compat as base_compat
from opportunity_engine.discovery.germany_riegermann import (
    RiegermannUrlIdentity,
    canonicalize_riegermann_url,
)

_QUERY_CATALOG_PATH = "/de/objekte"
_RESULT_COUNT_RE = re.compile(
    r"\b(?P<count>[0-9][0-9.\s]*)\s+Ergebnisse\b",
    re.I,
)
_HREF_RE = re.compile(r"href\s*=\s*[\"'](?P<href>[^\"']+)[\"']", re.I)


@dataclass(frozen=True, slots=True)
class RiegermannCatalogPaginationPlan:
    urls: tuple[str, ...]
    accid: str | None
    total_results: int | None
    page_size: int | None
    expected_page_count: int | None
    evidence_found: bool
    errors: tuple[str, ...]


def _normalized_host(host: str | None) -> str:
    value = (host or "").casefold()
    return value[4:] if value.startswith("www.") else value


def _positive_int(value: str | None, *, allow_zero: bool = False) -> int | None:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return None
    minimum = 0 if allow_zero else 1
    return parsed if parsed >= minimum else None


def _query_values(url: str) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for key, value in parse_qsl(urlparse(url).query, keep_blank_values=True):
        values.setdefault(key.casefold(), []).append(value)
    return values


def _query_catalog_accid(url: str) -> str | None:
    parsed = urlparse(url)
    if (
        _normalized_host(parsed.hostname) != "riegermann.de"
        or parsed.path.rstrip("/") != _QUERY_CATALOG_PATH
    ):
        return None
    values = _query_values(url).get("accid") or []
    if len(values) != 1:
        return None
    return values[0] if values[0].isdigit() else None


def _catalog_page_key(url: str) -> tuple[str, int] | None:
    values = _query_values(url)
    page_number = _positive_int((values.get("pagenumber") or [None])[-1])
    if page_number is not None:
        return ("page", page_number)
    offset = _positive_int(
        (values.get("currentpos") or [None])[-1],
        allow_zero=True,
    )
    if offset is not None:
        return ("offset", offset)
    return None


def _query_page_size(url: str) -> int | None:
    values = _query_values(url)
    return _positive_int((values.get("pagesize") or [None])[-1])


def _normalize_query_catalog_url(url: str) -> str | None:
    if _query_catalog_accid(url) is None:
        return None
    parsed = urlparse(url)
    return urlunparse(
        (
            "https",
            "riegermann.de",
            _QUERY_CATALOG_PATH,
            "",
            urlencode(parse_qsl(parsed.query, keep_blank_values=True), doseq=True),
            "",
        )
    )


def _replace_query_values(url: str, **updates: str | int | None) -> str:
    update_keys = {key.casefold() for key in updates}
    pairs = [
        (key, value)
        for key, value in parse_qsl(urlparse(url).query, keep_blank_values=True)
        if key.casefold() not in update_keys
    ]
    for key, value in updates.items():
        if value is not None:
            pairs.append((key, str(value)))
    parsed = urlparse(url)
    return urlunparse(
        (
            "https",
            "riegermann.de",
            _QUERY_CATALOG_PATH,
            "",
            urlencode(pairs, doseq=True),
            "",
        )
    )


def _result_count(source_html: str) -> int | None:
    visible = re.sub(r"<[^>]+>", " ", source_html)
    visible = " ".join(html.unescape(visible).split())
    match = _RESULT_COUNT_RE.search(visible)
    if not match:
        return None
    digits = re.sub(r"[^0-9]", "", match.group("count"))
    return int(digits) if digits else None


def _same_friendly_auction(
    candidate: str,
    expected: RiegermannUrlIdentity,
) -> bool:
    identity = canonicalize_riegermann_url(candidate)
    return bool(
        identity is not None
        and identity.kind == "AUCTION_CATALOG"
        and identity.auction_id == expected.auction_id
    )


def build_riegermann_catalog_pagination_plan(
    catalog_url: str,
    source_html: str,
) -> RiegermannCatalogPaginationPlan:
    """Resolve friendly and query-style catalog pagination conservatively."""
    identity = canonicalize_riegermann_url(catalog_url)
    if identity is None or identity.kind != "AUCTION_CATALOG":
        raise ValueError("catalog_url must be an exact Riegermann auction catalog")

    friendly_urls: list[str] = []
    query_urls_by_accid: dict[str, list[str]] = {}
    errors: list[str] = []

    for match in _HREF_RE.finditer(source_html):
        href = html.unescape(match.group("href")).strip()
        if not href:
            continue
        candidate = urljoin(catalog_url, href)
        if _same_friendly_auction(candidate, identity):
            if _catalog_page_key(candidate) is not None:
                friendly_urls.append(candidate)
            continue
        normalized_query = _normalize_query_catalog_url(candidate)
        if normalized_query is None:
            continue
        accid = _query_catalog_accid(normalized_query)
        if accid is not None:
            query_urls_by_accid.setdefault(accid, []).append(normalized_query)

    scope_accid: str | None = None
    scope_urls: list[str] = []
    if len(query_urls_by_accid) == 1:
        scope_accid, scope_urls = next(iter(query_urls_by_accid.items()))
    elif len(query_urls_by_accid) > 1:
        errors.append("multiple Accid catalog scopes were exposed by one auction page")

    total_results = _result_count(source_html)
    page_sizes = [
        size
        for url in scope_urls
        if (size := _query_page_size(url)) is not None
    ]
    page_size = max(page_sizes) if page_sizes else None
    linked_pages = [
        key[1]
        for url in scope_urls
        if (key := _catalog_page_key(url)) is not None and key[0] == "page"
    ]
    expected_page_count = None
    if total_results is not None and page_size is not None:
        expected_page_count = max(1, math.ceil(total_results / page_size))
    elif linked_pages:
        expected_page_count = max(linked_pages)

    planned: dict[tuple[str, int] | tuple[str, str], str] = {}
    for candidate in friendly_urls:
        key = _catalog_page_key(candidate)
        if key is None:
            continue
        normalized = urlunparse(
            (
                "https",
                "riegermann.de",
                urlparse(candidate).path,
                "",
                urlparse(candidate).query,
                "",
            )
        )
        planned.setdefault(key, normalized)

    if scope_urls:
        template = max(
            scope_urls,
            key=lambda item: (_query_page_size(item) or 0, len(item)),
        )
        if expected_page_count is not None:
            for page_number in range(1, expected_page_count + 1):
                generated = _replace_query_values(
                    template,
                    currentpos=None,
                    pagenumber=page_number,
                    pagesize=page_size,
                )
                planned[("page", page_number)] = generated
        else:
            for candidate in scope_urls:
                key = _catalog_page_key(candidate)
                if key is not None:
                    planned.setdefault(key, candidate)

    urls = tuple(
        planned[key]
        for key in sorted(planned, key=lambda item: (item[0], str(item[1])))
    )
    evidence_found = bool(
        friendly_urls
        or scope_urls
        or (total_results is not None and total_results > 0)
    )
    return RiegermannCatalogPaginationPlan(
        urls=urls,
        accid=scope_accid,
        total_results=total_results,
        page_size=page_size,
        expected_page_count=expected_page_count,
        evidence_found=evidence_found,
        errors=tuple(errors),
    )


def extract_riegermann_catalog_page_urls_query_compat(
    catalog_url: str,
    source_html: str,
) -> tuple[str, ...]:
    """Public helper returning the bounded query-aware pagination plan URLs."""
    return build_riegermann_catalog_pagination_plan(catalog_url, source_html).urls


def _fetch_query_catalog_page(
    url: str,
    *,
    expected_accid: str,
    expected_auction_id: str,
    session: Any,
    timeout: float,
    max_response_bytes: int,
) -> live_layer.RiegermannPublicPage:
    normalized = _normalize_query_catalog_url(url)
    if normalized is None or _query_catalog_accid(normalized) != expected_accid:
        raise ValueError("query catalog URL changed the expected Accid scope")

    response = session.get(
        normalized,
        timeout=timeout,
        allow_redirects=True,
        headers={
            "User-Agent": live_layer.DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    response.raise_for_status()

    final_url = str(response.url)
    final_query_scope = _query_catalog_accid(final_url)
    final_identity = canonicalize_riegermann_url(final_url)
    if not (
        final_query_scope == expected_accid
        or (
            final_identity is not None
            and final_identity.kind == "AUCTION_CATALOG"
            and final_identity.auction_id == expected_auction_id
        )
    ):
        raise RuntimeError("Riegermann query pagination redirected outside its catalog scope")

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

    canonical_url = (
        final_identity.canonical_url if final_identity is not None else normalized
    )
    return live_layer.RiegermannPublicPage(
        requested_url=normalized,
        final_url=final_url,
        canonical_url=canonical_url,
        identity_kind="AUCTION_CATALOG",
        auction_id=expected_auction_id,
        object_id=None,
        status_code=int(response.status_code),
        content_type=content_type,
        response_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        html=decoded,
    )


class _QueryAwarePaginatedCatalogSession:
    def __init__(
        self,
        catalog_url: str,
        *,
        upstream: Any,
        timeout: float,
        max_response_bytes: int,
        page_limit: int,
    ) -> None:
        identity = canonicalize_riegermann_url(catalog_url)
        if identity is None or identity.kind != "AUCTION_CATALOG":
            raise ValueError("catalog_url must be an exact Riegermann auction catalog")
        self.catalog_url = catalog_url
        self.auction_id = str(identity.auction_id)
        self.upstream = upstream
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self.page_limit = page_limit
        self.catalog_page_urls: list[str] = []
        self.catalog_page_errors: list[dict[str, str]] = []
        self.catalog_coverage_complete = False
        self.catalog_limit_reached = False
        self.catalog_scope_accid: str | None = None
        self.catalog_total_results: int | None = None
        self.catalog_page_size: int | None = None
        self.catalog_expected_page_count: int | None = None
        self.catalog_pagination_evidence_found = False
        self.catalog_coverage_reason = "not_started"
        self._merged_response: base_compat._MergedResponse | None = None

    def get(self, url: str, **kwargs: Any) -> Any:
        identity = canonicalize_riegermann_url(url)
        if (
            identity is not None
            and identity.kind == "AUCTION_CATALOG"
            and identity.auction_id == self.auction_id
        ):
            if self._merged_response is None:
                self._merged_response = self._load_catalog()
            return self._merged_response
        return self.upstream.get(url, **kwargs)

    def _fetch_page(self, url: str) -> live_layer.RiegermannPublicPage:
        if _query_catalog_accid(url) is not None:
            if self.catalog_scope_accid is None:
                raise RuntimeError("query pagination scope was not established")
            return _fetch_query_catalog_page(
                url,
                expected_accid=self.catalog_scope_accid,
                expected_auction_id=self.auction_id,
                session=self.upstream,
                timeout=self.timeout,
                max_response_bytes=self.max_response_bytes,
            )
        return live_layer.fetch_riegermann_public_page(
            url,
            session=self.upstream,
            timeout=self.timeout,
            max_response_bytes=self.max_response_bytes,
        )

    def _load_catalog(self) -> base_compat._MergedResponse:
        first = live_layer.fetch_riegermann_public_page(
            self.catalog_url,
            session=self.upstream,
            timeout=self.timeout,
            max_response_bytes=self.max_response_bytes,
        )
        self.catalog_page_urls.append(first.requested_url)

        item_urls = list(
            base_compat.extract_riegermann_item_urls_compat(
                first.canonical_url,
                first.html,
            )
        )
        seen_items = set(item_urls)
        initial_plan = build_riegermann_catalog_pagination_plan(
            self.catalog_url,
            first.html,
        )
        self.catalog_scope_accid = initial_plan.accid
        self.catalog_total_results = initial_plan.total_results
        self.catalog_page_size = initial_plan.page_size
        self.catalog_expected_page_count = initial_plan.expected_page_count
        self.catalog_pagination_evidence_found = initial_plan.evidence_found
        self.catalog_page_errors.extend(
            {"url": self.catalog_url, "error": error}
            for error in initial_plan.errors
        )

        queued: dict[tuple[str, int] | tuple[str, str], str] = {}
        for page_url in initial_plan.urls:
            key = _catalog_page_key(page_url) or ("url", page_url)
            queued.setdefault(key, page_url)
        visited: set[tuple[str, int] | tuple[str, str]] = set()
        fetched_query_pages: set[int] = set()

        while queued and len(self.catalog_page_urls) < self.page_limit:
            key = min(queued, key=lambda item: (item[0], str(item[1])))
            page_url = queued.pop(key)
            if key in visited:
                continue
            visited.add(key)
            try:
                page = self._fetch_page(page_url)
            except Exception as exc:
                self.catalog_page_errors.append(
                    {"url": page_url, "error": str(exc)}
                )
                continue

            self.catalog_page_urls.append(page.requested_url)
            if key[0] == "page" and isinstance(key[1], int):
                fetched_query_pages.add(key[1])

            page_items = base_compat.extract_riegermann_item_urls_compat(
                self.catalog_url,
                page.html,
            )
            new_items = [item for item in page_items if item not in seen_items]
            if not new_items:
                self.catalog_page_errors.append(
                    {
                        "url": page_url,
                        "error": "pagination page produced no new item URLs",
                    }
                )
            else:
                item_urls.extend(new_items)
                seen_items.update(new_items)

            discovered = build_riegermann_catalog_pagination_plan(
                self.catalog_url,
                page.html,
            )
            if self.catalog_scope_accid is None and discovered.accid is not None:
                self.catalog_scope_accid = discovered.accid
            if (
                discovered.accid is not None
                and self.catalog_scope_accid is not None
                and discovered.accid != self.catalog_scope_accid
            ):
                self.catalog_page_errors.append(
                    {
                        "url": page_url,
                        "error": "pagination page changed Accid scope",
                    }
                )
                continue
            for error in discovered.errors:
                self.catalog_page_errors.append({"url": page_url, "error": error})
            for discovered_url in discovered.urls:
                discovered_key = _catalog_page_key(discovered_url) or (
                    "url",
                    discovered_url,
                )
                if discovered_key not in visited:
                    queued.setdefault(discovered_key, discovered_url)

        self.catalog_limit_reached = bool(queued)
        expected_pages_fetched = (
            self.catalog_expected_page_count is not None
            and len(fetched_query_pages) >= self.catalog_expected_page_count
        )
        direct_pagination_complete = (
            self.catalog_expected_page_count is None
            and self.catalog_pagination_evidence_found
            and len(self.catalog_page_urls) > 1
            and not queued
        )

        if self.catalog_limit_reached:
            self.catalog_coverage_reason = "catalog_page_limit_reached"
        elif self.catalog_page_errors:
            self.catalog_coverage_reason = "catalog_page_errors"
        elif not self.catalog_pagination_evidence_found:
            self.catalog_coverage_reason = "pagination_not_proven"
        elif self.catalog_expected_page_count is not None and not expected_pages_fetched:
            self.catalog_coverage_reason = "expected_pages_not_fetched"
        elif expected_pages_fetched or direct_pagination_complete:
            self.catalog_coverage_reason = "complete"
        else:
            self.catalog_coverage_reason = "pagination_not_proven"

        self.catalog_coverage_complete = self.catalog_coverage_reason == "complete"

        anchors = "\n".join(
            f'<a href="{url}">{html.escape(urlparse(url).path.rsplit("/", 1)[-1])}</a>'
            for url in item_urls
        )
        merged_html = (
            first.html
            + "\n<section data-opportunity-engine-catalog-pagination=\"true\">\n"
            + anchors
            + "\n</section>\n"
        )
        return base_compat._MergedResponse(
            url=first.final_url,
            content=merged_html.encode("utf-8", errors="replace"),
            status_code=first.status_code,
            content_type=first.content_type or "text/html; charset=utf-8",
            encoding="utf-8",
        )


def _apply_query_catalog_coverage(
    live: live_layer.RiegermannLiveResult,
    session: _QueryAwarePaginatedCatalogSession,
) -> None:
    base_compat._apply_catalog_coverage(live, session)
    diagnostics = live.discovery_result["search_run_report"]["riegermann_live"]
    diagnostics.update(
        {
            "catalog_scope_accid": session.catalog_scope_accid,
            "catalog_total_results": session.catalog_total_results,
            "catalog_page_size": session.catalog_page_size,
            "catalog_expected_page_count": session.catalog_expected_page_count,
            "catalog_pagination_evidence_found": (
                session.catalog_pagination_evidence_found
            ),
            "catalog_coverage_reason": session.catalog_coverage_reason,
        }
    )
    parent = next(
        (
            candidate
            for candidate in live.discovery_result["all_discovered_candidates"]
            if candidate.get("page_role") == "AUCTION_EVENT"
        ),
        None,
    )
    if parent is None:
        return
    parent.update(
        {
            "catalog_scope_accid": session.catalog_scope_accid,
            "catalog_total_results": session.catalog_total_results,
            "catalog_expected_page_count": session.catalog_expected_page_count,
            "catalog_pagination_evidence_found": (
                session.catalog_pagination_evidence_found
            ),
            "catalog_coverage_reason": session.catalog_coverage_reason,
        }
    )
    if session.catalog_coverage_reason == "pagination_not_proven":
        parent["next_verification_step"] = (
            "Resolve public Riegermann query-style pagination before treating "
            "the catalog as complete."
        )


def run_riegermann_live_discovery_query_compat(
    catalog_url: str,
    *,
    information_url: str | None = None,
    session: Any | None = None,
    timeout: float = 20.0,
    max_response_bytes: int = live_layer.DEFAULT_MAX_RESPONSE_BYTES,
    item_verification_limit: int = 10,
    catalog_page_limit: int = 100,
) -> live_layer.RiegermannLiveResult:
    """Run the live adapter with query-aware, bounded catalog pagination."""
    if catalog_page_limit < 1 or catalog_page_limit > 200:
        raise ValueError("catalog_page_limit must be between 1 and 200")

    paginated_session = _QueryAwarePaginatedCatalogSession(
        catalog_url,
        upstream=session or live_layer.requests,
        timeout=timeout,
        max_response_bytes=max_response_bytes,
        page_limit=catalog_page_limit,
    )
    live = base_compat._ORIGINAL_RUN_RIEGERMANN_LIVE_DISCOVERY(
        catalog_url,
        information_url=information_url,
        session=paginated_session,
        timeout=timeout,
        max_response_bytes=max_response_bytes,
        item_verification_limit=item_verification_limit,
    )
    _apply_query_catalog_coverage(live, paginated_session)
    return live


def install_riegermann_query_catalog_compatibility() -> None:
    """Install fixture compatibility plus query-style catalog pagination."""
    base_compat.install_riegermann_live_catalog_compatibility()
    live_layer.run_riegermann_live_discovery = (
        run_riegermann_live_discovery_query_compat
    )
