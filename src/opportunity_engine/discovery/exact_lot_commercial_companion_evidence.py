"""Bounded same-domain commercial companion evidence for strict Exact-Lots.

Exact-Lot item pages sometimes prove the lot, price and quantity but omit site-level
company or fulfilment information.  This module may inspect a tiny, explicit set of
same-domain companion pages (for example contact, terms or delivery pages) that are
already linked from a verified commercial root.

Companion pages are context only.  They never prove the Exact-Lot, never prove lot
condition, never change qualification, and never perform search, contact, bidding,
reservation, purchase or payment.
"""
from __future__ import annotations

from html.parser import HTMLParser
from typing import Any
from urllib.parse import unquote, urldefrag, urljoin, urlsplit

from opportunity_engine.discovery.exact_lot_child_link_resolution import (
    AggregateHtmlFetcher,
    fetch_public_html,
)
from opportunity_engine.discovery.keyword_shadow_verification import _public_https_url
from opportunity_engine.discovery.source_native_commercial_terms_capture import (
    capture_source_native_commercial_terms,
)

SCHEMA_VERSION = "exact-lot-commercial-companion-evidence-1.0"
MAX_COMPANION_LINKS = 2
MAX_COMPANION_PAGE_FETCHES = 2

_ROLE_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "FULFILMENT",
        (
            "shipping",
            "delivery",
            "frakt",
            "leverans",
            "levering",
            "versand",
            "lieferung",
            "abholung",
            "pickup",
        ),
    ),
    (
        "SELLER_IDENTITY",
        (
            "contact",
            "kontakt",
            "kontakta",
            "about",
            "about-us",
            "om-oss",
            "omoss",
            "company",
            "foretag",
            "företag",
            "firma",
            "impressum",
            "ueber-uns",
            "uber-uns",
            "über-uns",
        ),
    ),
    (
        "TERMS",
        (
            "terms",
            "conditions",
            "villkor",
            "kopvillkor",
            "köpvillkor",
            "saljvillkor",
            "säljvillkor",
            "vilkar",
            "vilkår",
            "betingelser",
            "agb",
        ),
    ),
)
_ROLE_PRIORITY = {"FULFILMENT": 0, "SELLER_IDENTITY": 1, "TERMS": 2}


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalized_host(url: str) -> str:
    try:
        return (urlsplit(_compact(url)).hostname or "").casefold().removeprefix("www.").rstrip(".")
    except ValueError:
        return ""


def _companion_role(url: str) -> str | None:
    try:
        path = unquote(urlsplit(_compact(url)).path or "/").casefold()
    except ValueError:
        return None
    normalized = path.replace("_", "-")
    tokens = normalized.replace("/", "-").split("-")
    searchable = " ".join(token for token in tokens if token)
    for role, markers in _ROLE_MARKERS:
        if any(marker in searchable for marker in markers):
            return role
    return None


class _HrefParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a":
            return
        for key, value in attrs:
            if key.casefold() == "href" and value:
                self.hrefs.append(value.strip())
                return


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            value = _compact(data)
            if value:
                self.parts.append(value)


def _visible_text(html_text: str) -> str:
    parser = _VisibleTextParser()
    try:
        parser.feed(str(html_text or ""))
    except (TypeError, ValueError):
        return ""
    return "\n".join(parser.parts)


def extract_same_domain_commercial_companion_links(
    *,
    page_url: str,
    html_text: str,
    max_links: int = MAX_COMPANION_LINKS,
) -> list[dict[str, str]]:
    """Return a bounded ordered set of explicit same-domain companion links."""
    if not 1 <= max_links <= MAX_COMPANION_LINKS:
        raise ValueError(f"max_links must be between 1 and {MAX_COMPANION_LINKS}")
    page = _compact(page_url)
    page_host = _normalized_host(page)
    if not _public_https_url(page) or not page_host:
        return []

    parser = _HrefParser()
    try:
        parser.feed(str(html_text or ""))
    except (TypeError, ValueError):
        return []

    current = urldefrag(page).url
    candidates: list[tuple[int, int, str, str]] = []
    seen: set[str] = set()
    for position, href in enumerate(parser.hrefs):
        try:
            candidate = urldefrag(urljoin(page, href)).url
            parts = urlsplit(candidate)
        except ValueError:
            continue
        if parts.scheme.casefold() != "https" or _normalized_host(candidate) != page_host:
            continue
        if candidate == current or candidate in seen:
            continue
        role = _companion_role(candidate)
        if role is None:
            continue
        seen.add(candidate)
        candidates.append((_ROLE_PRIORITY[role], position, candidate, role))

    candidates.sort(key=lambda item: (item[0], item[1]))
    return [
        {"url": candidate, "role": role}
        for _, _, candidate, role in candidates[:max_links]
    ]


def _bounded_merge(values: list[str], additions: object, *, limit: int = 8) -> None:
    if not isinstance(additions, (list, tuple)):
        return
    seen = {value.casefold() for value in values}
    for raw in additions:
        value = _compact(raw)
        key = value.casefold()
        if not value or key in seen:
            continue
        seen.add(key)
        values.append(value)
        if len(values) >= limit:
            return


def capture_same_domain_commercial_companion_evidence(
    companion_links: list[dict[str, str]],
    *,
    root_url: str,
    aggregate_fetcher: AggregateHtmlFetcher = fetch_public_html,
    max_page_fetches: int = MAX_COMPANION_PAGE_FETCHES,
) -> dict[str, Any]:
    """Fetch bounded companion pages and retain explicit context without promotion."""
    if not 1 <= max_page_fetches <= MAX_COMPANION_PAGE_FETCHES:
        raise ValueError(
            f"max_page_fetches must be between 1 and {MAX_COMPANION_PAGE_FETCHES}"
        )
    root_host = _normalized_host(root_url)
    pages: list[dict[str, Any]] = []
    seller_candidates: list[str] = []
    fulfilment_candidates: list[str] = []
    observed_condition_candidates: list[str] = []
    attempted = 0
    succeeded = 0

    for raw in companion_links[:max_page_fetches]:
        url = _compact(raw.get("url"))
        role = _compact(raw.get("role"))
        if not url or not root_host or _normalized_host(url) != root_host or not _public_https_url(url):
            continue
        attempted += 1
        fetched = aggregate_fetcher(url)
        final_url = _compact(fetched.final_url or url)
        if not fetched.ok or _normalized_host(final_url) != root_host:
            pages.append(
                {
                    "url": url,
                    "role": role,
                    "fetch_ok": False,
                    "status_code": fetched.status_code,
                    "final_url": final_url,
                    "fetch_error": fetched.error or "COMPANION_REDIRECT_LEFT_DOMAIN",
                    "seller_identity_candidates": [],
                    "fulfilment_candidates": [],
                    "observed_condition_candidates": [],
                }
            )
            continue

        succeeded += 1
        captured = capture_source_native_commercial_terms(_visible_text(fetched.html))
        page_seller = list(captured.get("seller_identity_candidates") or [])
        page_fulfilment = list(captured.get("fulfilment_candidates") or [])
        page_condition = list(captured.get("condition_candidates") or [])
        _bounded_merge(seller_candidates, page_seller)
        _bounded_merge(fulfilment_candidates, page_fulfilment)
        _bounded_merge(observed_condition_candidates, page_condition)
        pages.append(
            {
                "url": url,
                "role": role,
                "fetch_ok": True,
                "status_code": fetched.status_code,
                "final_url": final_url,
                "fetch_error": None,
                "seller_identity_candidates": page_seller,
                "fulfilment_candidates": page_fulfilment,
                "observed_condition_candidates": page_condition,
            }
        )

    evidence_found = bool(seller_candidates or fulfilment_candidates)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS" if evidence_found else "VALID_ZERO",
        "root_url": _compact(root_url),
        "same_domain_only": True,
        "max_page_fetches": max_page_fetches,
        "page_fetches_attempted": attempted,
        "page_fetches_succeeded": succeeded,
        "pages": pages,
        "seller_identity_candidates": seller_candidates,
        "fulfilment_candidates": fulfilment_candidates,
        "observed_condition_candidates": observed_condition_candidates,
        "lot_condition_evidence_allowed": False,
        "companion_evidence_is_qualification_evidence": False,
        "companion_evidence_is_financial_analysis_evidence": False,
        "search_request_count": 0,
        "paid_search_request_count": 0,
        "production_mutation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
