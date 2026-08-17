"""Native live discovery for public Blinto auctions in Sweden.

BLINTO_NATIVE_LIVE_DISCOVERY_V1 deliberately bypasses search engines. It reads
Blinto's public live-auction listing, keeps only exact clothing-inventory auction
links, and leaves ACTIVE/ENDED truth to the existing exact-page Blinto verifier.
No login, bidding, contact, purchase, or access-control bypass is performed.
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

import requests

from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    ENDED,
    ITEM_LISTING,
    UNKNOWN,
    DiscoveryQuery,
    PageVerification,
)
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.sweden_blinto import (
    blinto_gate_decision,
    canonicalize_blinto_auction_url,
    verify_blinto_public_page,
)

BLINTO_NATIVE_LIVE_DISCOVERY_POLICY = "BLINTO_NATIVE_LIVE_DISCOVERY_V1"
BLINTO_LIVE_LISTING_URL = "https://www.blinto.se/auction/l/"
BLINTO_NATIVE_QUERY = DiscoveryQuery(
    "se-bl-native-01",
    "WAREHOUSE_SURPLUS",
    "SALE_INTENT",
    "CLOTHING_INVENTORY",
    "Blinto native live klær vareparti auksjon",
)
_SOURCE_POLICY_ALIASES = "klær vareparti auksjon"

# Native listing titles are structured source data, so require whole-term matches.
# This prevents substrings such as Swedish "skor" (shoes) inside "manskapskorg".
_NATIVE_CLOTHING_TITLE_TERMS = (
    "kläder",
    "arbetskläder",
    "yrkeskläder",
    "varselkläder",
    "skyddskläder",
    "damkläder",
    "herrkläder",
    "barnkläder",
    "sportkläder",
    "träningskläder",
    "arbetsbyxor",
    "byxor",
    "jackor",
    "jacka",
    "varseljackor",
    "skaljackor",
    "arbetsjackor",
    "tröjor",
    "t-shirts",
    "piké",
    "skjortor",
    "shorts",
    "västar",
    "overaller",
    "regnkläder",
    "arbetsskor",
    "skyddsskor",
    "skor",
    "stövlar",
    "plagg",
)
_NATIVE_BULK_TERMS = (
    "varulager",
    "restlager",
    "restparti",
    "överskott",
    "parti",
    "sortiment",
    "hela lagret",
    "pall",
    "pallar",
    "kartong",
    "kartonger",
    "stycken",
    "plagg",
)
_NATIVE_QUANTITY_RE = re.compile(
    r"\b(?:totalt\s+antal\s*:?\s*)?(?P<count>\d{1,7})\s*"
    r"(?:st|stycken|plagg|artiklar|enheter|delar|byxor|par)\b",
    re.I,
)


def _contains_exact_term(text: str, term: str) -> bool:
    normalized = " ".join((text or "").casefold().split())
    pattern = rf"(?<!\w){re.escape(term.casefold())}(?!\w)"
    return re.search(pattern, normalized, re.I) is not None


def _native_title_has_clothing(title: str) -> bool:
    return any(_contains_exact_term(title, term) for term in _NATIVE_CLOTHING_TITLE_TERMS)


def _native_has_bulk_scope(text: str) -> bool:
    return any(_contains_exact_term(text, term) for term in _NATIVE_BULK_TERMS) or bool(
        _NATIVE_QUANTITY_RE.search(text or "")
    )


def _native_quantity(text: str) -> int | None:
    match = _NATIVE_QUANTITY_RE.search(text or "")
    return int(match.group("count")) if match else None


def _native_inventory_type(text: str) -> str:
    normalized = " ".join((text or "").casefold().split())
    if any(
        _contains_exact_term(normalized, term)
        for term in (
            "arbetskläder",
            "yrkeskläder",
            "varselkläder",
            "skyddskläder",
            "arbetsbyxor",
            "varseljackor",
            "arbetsjackor",
            "arbetsskor",
            "skyddsskor",
        )
    ):
        return "workwear_inventory"
    return "mixed_clothing_inventory"


def _repair_native_verification(verification: PageVerification) -> PageVerification:
    """Restore bounded clothing evidence when Blinto text contains incidental fixture words.

    Blinto clothing lots can explicitly say that hangers/shop fittings are *not*
    included. The generic verifier conservatively treats words such as ``galgar``
    as equipment noise. For the native path we already have an exact Blinto item
    identity and a source-native title, so clothing/bulk scope is re-established
    only when the exact page title itself contains a whole clothing term and the
    bounded page context proves bulk scope.
    """
    if not (
        verification.verified
        and verification.page_role == ITEM_LISTING
        and verification.identity_stable
    ):
        return verification

    title = verification.title or ""
    context = " ".join(
        value
        for value in (verification.title, verification.text, verification.bounded_context)
        if value
    )
    if not _native_title_has_clothing(title) or not _native_has_bulk_scope(context):
        return verification

    quantity = verification.quantity or _native_quantity(context)
    sale_evidence = verification.sale_evidence or verification.listing_status in {
        ACTIVE,
        ENDED,
    }
    return replace(
        verification,
        clothing_inventory_evidence=True,
        sale_evidence=sale_evidence,
        inventory_type=verification.inventory_type or _native_inventory_type(context),
        quantity=quantity,
    )


class _AuctionAnchorParser(HTMLParser):
    """Collect text for public links whose path can be an exact Blinto auction."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._href: str | None = None
        self._text: list[str] = []
        self.anchors: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a" or self._href is not None:
            return
        href = next((value for key, value in attrs if key.casefold() == "href"), None)
        if href and "/auction/" in href:
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self._href is None:
            return
        title = " ".join(" ".join(self._text).split())
        self.anchors.append((self._href, title))
        self._href = None
        self._text = []


@dataclass(frozen=True, slots=True)
class NativeListingFetch:
    final_url: str
    html: str


FetchListing = Callable[[str, float], NativeListingFetch]
PageVerifier = Callable[[str], PageVerification]


def _fetch_listing(url: str, timeout: float) -> NativeListingFetch:
    response = requests.get(
        url,
        timeout=timeout,
        allow_redirects=True,
        headers={"User-Agent": "OpportunityEngine-Discovery/2.1"},
    )
    response.raise_for_status()
    return NativeListingFetch(final_url=response.url, html=response.text)


def _parse_native_hits(html_text: str, *, base_url: str) -> tuple[SearchHit, ...]:
    parser = _AuctionAnchorParser()
    parser.feed(html_text)

    # Blinto commonly exposes the same auction through image and title anchors.
    # Keep one occurrence identity and prefer the most informative anchor text.
    best_by_url: dict[str, SearchHit] = {}
    for href, anchor_text in parser.anchors:
        absolute = urljoin(base_url, href)
        identity = canonicalize_blinto_auction_url(absolute)
        if identity is None:
            continue
        hit = SearchHit(
            title=anchor_text,
            url=identity.canonical_url,
            description=f"source policy aliases: {_SOURCE_POLICY_ALIASES}",
            provider=BLINTO_NATIVE_LIVE_DISCOVERY_POLICY,
        )
        previous = best_by_url.get(identity.canonical_url)
        if previous is None or len(hit.title) > len(previous.title):
            best_by_url[identity.canonical_url] = hit
    return tuple(best_by_url.values())


class BlintoNativeLiveSearchProvider:
    """SearchProvider-compatible reader for Blinto's public live listing page."""

    name = "Blinto native live listing"

    def __init__(
        self,
        *,
        listing_url: str = BLINTO_LIVE_LISTING_URL,
        timeout: float = 15.0,
        fetch_listing: FetchListing | None = None,
    ) -> None:
        self._listing_url = listing_url
        self._timeout = timeout
        self._fetch_listing = fetch_listing or _fetch_listing
        self._loaded = False
        self._accepted: tuple[SearchHit, ...] = ()
        self._listing_requests = 0
        self._raw_exact_links = 0
        self._rejected_hits = 0
        self._rejection_reasons: Counter[str] = Counter()
        self._accepted_samples: list[dict[str, Any]] = []
        self._rejected_samples: list[dict[str, Any]] = []
        self._final_listing_url: str | None = None

    def _load(self) -> None:
        if self._loaded:
            return
        fetched = self._fetch_listing(self._listing_url, self._timeout)
        self._listing_requests += 1
        self._final_listing_url = fetched.final_url
        raw_hits = _parse_native_hits(fetched.html, base_url=fetched.final_url)
        self._raw_exact_links = len(raw_hits)

        accepted: list[SearchHit] = []
        for hit in raw_hits:
            decision = blinto_gate_decision(hit)
            accepted_by_native_title = decision.accepted and _native_title_has_clothing(
                hit.title
            )
            reason = decision.reason
            if decision.accepted and not accepted_by_native_title:
                reason = "specific Blinto title lacks exact clothing term"
            sample = {
                "title": hit.title,
                "url": hit.url,
                "listing_key": decision.listing_key,
                "object_id": decision.object_id,
                "occurrence_id": decision.occurrence_id,
                "reason": reason,
            }
            if not accepted_by_native_title:
                self._rejected_hits += 1
                self._rejection_reasons[reason] += 1
                if len(self._rejected_samples) < 30:
                    self._rejected_samples.append(sample)
                continue
            accepted.append(
                SearchHit(
                    title=hit.title,
                    url=decision.canonical_url,
                    description=hit.description,
                    provider=self.name,
                )
            )
            if len(self._accepted_samples) < 30:
                self._accepted_samples.append(sample)

        self._accepted = tuple(accepted)
        self._loaded = True

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        if query != BLINTO_NATIVE_QUERY.query:
            raise ValueError("query is not registered in BLINTO_NATIVE_LIVE_DISCOVERY_V1")
        if count < 1:
            raise ValueError("count must be positive")
        self._load()
        return self._accepted[:count]

    def diagnostics(self) -> dict[str, Any]:
        return {
            "policy": BLINTO_NATIVE_LIVE_DISCOVERY_POLICY,
            "source": "BLINTO",
            "source_mode": "NATIVE_LIVE_LISTING",
            "listing_url": self._listing_url,
            "final_listing_url": self._final_listing_url,
            "listing_requests": self._listing_requests,
            "brave_requests": 0,
            "paid_search_used": False,
            "native_exact_title_filter": True,
            "raw_exact_auction_links": self._raw_exact_links,
            "accepted_hits": len(self._accepted),
            "rejected_hits": self._rejected_hits,
            "accepted_samples": list(self._accepted_samples),
            "rejection_reasons": dict(sorted(self._rejection_reasons.items())),
            "rejected_samples": list(self._rejected_samples),
        }


class BlintoNativeLiveVerifier:
    """Count exact source-page checks and preserve source lifecycle truth."""

    def __init__(self, delegate: PageVerifier = verify_blinto_public_page) -> None:
        self._delegate = delegate
        self._attempts = 0
        self._verified = 0
        self._statuses: Counter[str] = Counter()
        self._native_evidence_repairs = 0

    def __call__(self, url: str) -> PageVerification:
        self._attempts += 1
        original = self._delegate(url)
        verification = _repair_native_verification(original)
        if verification != original:
            self._native_evidence_repairs += 1
        if verification.verified:
            self._verified += 1
        status = verification.listing_status or UNKNOWN
        self._statuses[str(status)] += 1
        return verification

    def diagnostics(self) -> dict[str, Any]:
        return {
            "policy": BLINTO_NATIVE_LIVE_DISCOVERY_POLICY,
            "exact_page_verification_attempts": self._attempts,
            "verified_pages": self._verified,
            "active_pages": self._statuses.get(ACTIVE, 0),
            "ended_pages": self._statuses.get(ENDED, 0),
            "unknown_pages": self._statuses.get(UNKNOWN, 0),
            "native_evidence_repairs": self._native_evidence_repairs,
            "brave_requests": 0,
        }


def build_blinto_native_live_queries() -> tuple[DiscoveryQuery, ...]:
    """Return the single provider-contract query used by the generic engine."""
    return (BLINTO_NATIVE_QUERY,)
