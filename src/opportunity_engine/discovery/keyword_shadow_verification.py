"""Second-stage verification for the three Italy keyword SHADOW survivors.

This module freezes the three survivors from KEYWORD_DISCOVERY_LAB_V1 and
re-evaluates them with the exact same scoring weights/thresholds after fetching
source pages directly. The search budget is three queries and the page budget
is fifteen pages (3 x 5). It is shadow-only and cannot promote keywords into
production automatically.
"""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import ipaddress
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

import requests

from opportunity_engine.discovery.keyword_discovery_lab import (
    KeywordCandidate,
    run_keyword_discovery_lab,
    score_keyword,
)
from opportunity_engine.discovery.search_provider import SearchHit


SCHEMA_VERSION = "keyword-shadow-verification-1.0"
LAB_FAMILY = "KEYWORD_SHADOW_VERIFICATION_V1"
RESULTS_PER_KEYWORD = 5
MAX_PAGE_FETCHES = 15
MAX_RESPONSE_BYTES = 600_000
MAX_TEXT_CHARS = 120_000

SHADOW_CANDIDATES: tuple[KeywordCandidate, ...] = (
    KeywordCandidate(
        "it-lotti-fallimentari",
        "BANKRUPTCY_LOTS",
        "lotti fallimentari abbigliamento",
    ),
    KeywordCandidate(
        "it-vendita-stock-magazzino",
        "WAREHOUSE_STOCK_SALE",
        "vendita stock abbigliamento magazzino",
    ),
    KeywordCandidate(
        "it-stock-ingrosso",
        "STOCK_WHOLESALE",
        "stock abbigliamento ingrosso",
    ),
)


@dataclass(frozen=True, slots=True)
class PageFetchResult:
    requested_url: str
    final_url: str
    ok: bool
    status_code: int | None
    title: str
    text: str
    error: str | None = None
    truncated: bool = False


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._in_title = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.casefold()
        if normalized in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if normalized == "title" and self._skip_depth == 0:
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()
        if normalized == "title":
            self._in_title = False
        if normalized in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        value = " ".join(data.split()).strip()
        if not value:
            return
        self.text_parts.append(value)
        if self._in_title:
            self.title_parts.append(value)


def _public_https_url(raw_url: str) -> bool:
    try:
        parsed = urlsplit(str(raw_url or "").strip())
    except ValueError:
        return False
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.casefold().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _parse_html(body: bytes, encoding: str | None) -> tuple[str, str]:
    text = body.decode(encoding or "utf-8", errors="replace")
    parser = _VisibleTextParser()
    parser.feed(text)
    title = " ".join(parser.title_parts).strip()
    visible = " ".join(parser.text_parts).strip()
    return title[:1000], visible[:MAX_TEXT_CHARS]


def fetch_public_page(url: str) -> PageFetchResult:
    """Fetch one bounded public HTTPS page for evidence-only verification."""
    requested = str(url or "").strip()
    if not _public_https_url(requested):
        return PageFetchResult(
            requested_url=requested,
            final_url=requested,
            ok=False,
            status_code=None,
            title="",
            text="",
            error="UNSAFE_OR_UNSUPPORTED_URL",
        )

    try:
        with requests.get(
            requested,
            timeout=(5, 12),
            allow_redirects=True,
            stream=True,
            headers={
                "User-Agent": "opportunity-engine-keyword-shadow-verifier/1.0",
                "Accept": "text/html,application/xhtml+xml",
            },
        ) as response:
            final_url = str(response.url or requested)
            if not _public_https_url(final_url):
                return PageFetchResult(
                    requested_url=requested,
                    final_url=final_url,
                    ok=False,
                    status_code=response.status_code,
                    title="",
                    text="",
                    error="UNSAFE_REDIRECT_TARGET",
                )
            if response.status_code < 200 or response.status_code >= 300:
                return PageFetchResult(
                    requested_url=requested,
                    final_url=final_url,
                    ok=False,
                    status_code=response.status_code,
                    title="",
                    text="",
                    error=f"HTTP_{response.status_code}",
                )
            content_type = str(response.headers.get("Content-Type") or "").casefold()
            if "html" not in content_type:
                return PageFetchResult(
                    requested_url=requested,
                    final_url=final_url,
                    ok=False,
                    status_code=response.status_code,
                    title="",
                    text="",
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
            title, text = _parse_html(body, response.encoding)
            if not text:
                return PageFetchResult(
                    requested_url=requested,
                    final_url=final_url,
                    ok=False,
                    status_code=response.status_code,
                    title=title,
                    text="",
                    error="EMPTY_PAGE_TEXT",
                    truncated=truncated,
                )
            return PageFetchResult(
                requested_url=requested,
                final_url=final_url,
                ok=True,
                status_code=response.status_code,
                title=title,
                text=text,
                error=None,
                truncated=truncated,
            )
    except requests.RequestException as exc:
        return PageFetchResult(
            requested_url=requested,
            final_url=requested,
            ok=False,
            status_code=None,
            title="",
            text="",
            error=f"{type(exc).__name__}: {str(exc)[:200]}",
        )


PageFetcher = Callable[[str], PageFetchResult]


def run_keyword_shadow_verification(
    *,
    environment: Mapping[str, str] | None = None,
    provider_factory=None,
    page_fetcher: PageFetcher = fetch_public_page,
    freshness: str | None = None,
) -> dict[str, Any]:
    """Re-score the frozen three SHADOW queries using direct-page evidence."""
    kwargs: dict[str, Any] = {
        "environment": environment or {},
        "candidates": SHADOW_CANDIDATES,
        "keyword_limit": len(SHADOW_CANDIDATES),
        "results_per_keyword": RESULTS_PER_KEYWORD,
        "freshness": freshness,
    }
    if provider_factory is not None:
        kwargs["provider_factory"] = provider_factory

    discovery = run_keyword_discovery_lab(**kwargs)
    base: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "lab_family": LAB_FAMILY,
        "market": "IT",
        "frozen_keyword_count": len(SHADOW_CANDIDATES),
        "results_per_keyword": RESULTS_PER_KEYWORD,
        "max_page_fetches": MAX_PAGE_FETCHES,
        "same_v1_score_weights": True,
        "same_v1_decision_thresholds": True,
        "production_write_enabled": False,
        "promotion_to_live_engine_enabled": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
        "stage1_discovery_status": discovery.get("status"),
        "stage1_query_count": discovery.get("queries_attempted", 0),
        "stage1_errors": discovery.get("errors", []),
    }
    if discovery.get("status") in {"BLOCKED_CONFIGURATION", "BLOCKED_RETRIEVAL"}:
        return {
            **base,
            "status": discovery.get("status"),
            "block_reason": discovery.get("block_reason"),
            "verified_evaluations": [],
            "ranking": [],
            "promote_count": 0,
            "shadow_count": 0,
            "reject_count": 0,
            "page_fetches_attempted": 0,
            "page_fetches_succeeded": 0,
        }

    candidate_by_id = {candidate.keyword_id: candidate for candidate in SHADOW_CANDIDATES}
    verified_evaluations: list[dict[str, Any]] = []
    fetches_attempted = 0
    fetches_succeeded = 0

    for evaluation in discovery.get("evaluations", []):
        candidate = candidate_by_id.get(str(evaluation.get("keyword_id")))
        if candidate is None:
            continue
        verified_hits: list[SearchHit] = []
        page_evidence: list[dict[str, Any]] = []
        for original in list(evaluation.get("results") or [])[:RESULTS_PER_KEYWORD]:
            url = str(original.get("url") or "")
            if fetches_attempted >= MAX_PAGE_FETCHES:
                fetched = PageFetchResult(
                    requested_url=url,
                    final_url=url,
                    ok=False,
                    status_code=None,
                    title="",
                    text="",
                    error="PAGE_BUDGET_EXHAUSTED",
                )
            else:
                fetches_attempted += 1
                fetched = page_fetcher(url)
            if fetched.ok:
                fetches_succeeded += 1
                verified_hits.append(
                    SearchHit(
                        title=fetched.title or str(original.get("title") or ""),
                        url=fetched.final_url or url,
                        description=fetched.text,
                        provider="DIRECT_PAGE_VERIFICATION",
                    )
                )
            else:
                verified_hits.append(
                    SearchHit(
                        title="",
                        url=url,
                        description="",
                        provider="DIRECT_PAGE_VERIFICATION_FAILED",
                    )
                )
            page_evidence.append(
                {
                    "url": url,
                    "final_url": fetched.final_url,
                    "ok": fetched.ok,
                    "status_code": fetched.status_code,
                    "error": fetched.error,
                    "truncated": fetched.truncated,
                    "original_rank": original.get("rank"),
                }
            )

        rescored = score_keyword(candidate, verified_hits)
        coverage = (
            sum(1 for item in page_evidence if item["ok"]) / len(page_evidence)
            if page_evidence
            else 0.0
        )
        rescored["stage1_score"] = evaluation.get("score", 0.0)
        rescored["stage1_decision"] = evaluation.get("decision")
        rescored["verified_page_coverage"] = round(coverage, 4)
        rescored["page_evidence"] = page_evidence
        verified_evaluations.append(rescored)

    ranking = sorted(
        verified_evaluations,
        key=lambda item: (-float(item.get("score", 0.0)), str(item.get("query", ""))),
    )
    for rank, item in enumerate(ranking, start=1):
        item["rank"] = rank

    promote = sum(1 for item in ranking if item.get("decision") == "PROMOTE")
    shadow = sum(1 for item in ranking if item.get("decision") == "SHADOW")
    reject = sum(1 for item in ranking if item.get("decision") == "REJECT")
    status = "SUCCESS" if ranking else "VALID_ZERO"
    return {
        **base,
        "status": status,
        "block_reason": None,
        "verified_evaluations": verified_evaluations,
        "ranking": ranking,
        "promote_count": promote,
        "shadow_count": shadow,
        "reject_count": reject,
        "page_fetches_attempted": fetches_attempted,
        "page_fetches_succeeded": fetches_succeeded,
    }
