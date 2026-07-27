"""Fail-closed guard for generic inventory source channels.

The main verifier already distinguishes several page roles. This guard handles a
remaining ambiguity: a root company page can contain service descriptions, news
cases, locations and clothing terms from different sections and accidentally look
like one specific inventory listing.

The guard is generic. Named companies may appear in regression fixtures, but no
production rule is keyed to a domain or company name.
"""
from __future__ import annotations

from dataclasses import replace
from urllib.parse import urlparse

from opportunity_engine.discovery.clothing_inventory_search import (
    SOURCE_CHANNEL,
    UNKNOWN,
    UNVERIFIED_EVENT,
    PageVerification,
    normalize_public_url,
)

_GENERIC_CHANNEL_TITLES = (
    "kjøp og salg av varepartier",
    "kjop og salg av varepartier",
    "varepartier og overskuddsvarer",
    "kjøp og salg av varelager",
    "kjop og salg av varelager",
)

_SOURCE_CHANNEL_PHRASES = (
    "selge varepartier til oss",
    "kjøpe varepartier fra oss",
    "kjope varepartier fra oss",
    "vi kjøper ukurante",
    "vi kjoper ukurante",
    "vi selger overskuddsvarer",
    "stadig skiftende utvalg",
    "har du et varelager",
    "vi hjelper deg å selge varene",
    "ta kontakt",
)

_MULTI_CASE_MARKERS = (
    "aktuelt",
    "se flere nyheter",
    "konkursutsalg av",
    "to caser",
    "to skadetilfeller",
    "les mer",
)


def _normalized(*values: str | None) -> str:
    return " ".join(" ".join(value.casefold().split()) for value in values if value)


def _is_root_page(url: str) -> bool:
    canonical = normalize_public_url(url)
    if not canonical:
        return False
    return urlparse(canonical).path in {"", "/"}


def _generic_channel_evidence(result: PageVerification) -> bool:
    """Return True when one page describes a channel, not one sale object."""
    if not _is_root_page(result.url):
        return False

    title = _normalized(result.title)
    text = _normalized(result.title, result.text, result.bounded_context)
    title_is_generic = any(term in title for term in _GENERIC_CHANNEL_TITLES)
    channel_hits = sum(phrase in text for phrase in _SOURCE_CHANNEL_PHRASES)
    case_hits = sum(marker in text for marker in _MULTI_CASE_MARKERS)

    # A root page with a generic inventory-trading title and repeated buy/sell
    # service language is a channel. Multiple news/case markers strengthen the
    # conclusion that unrelated sections must not be combined into one listing.
    return (
        title_is_generic and channel_hits >= 2
    ) or (
        channel_hits >= 3 and case_hits >= 1
    )


def enforce_source_channel_identity(result: PageVerification) -> PageVerification:
    """Downgrade generic root inventory pages to ``SOURCE_CHANNEL``.

    The returned object intentionally clears all listing-scoped commercial fields.
    A source channel remains verified as a public page, but it is not an
    opportunity, has no stable opportunity identity and cannot enter Top 5.
    """
    if not _generic_channel_evidence(result):
        return result

    return replace(
        result,
        location=None,
        inventory_type=None,
        price_nok=None,
        bid_price_nok=None,
        quantity=None,
        listing_status=UNKNOWN,
        page_role=SOURCE_CHANNEL,
        opportunity_identity=None,
        identity_stable=False,
        clothing_inventory_evidence=False,
        sale_evidence=False,
        event_scenario=UNVERIFIED_EVENT,
        bounded_context=None,
        verified=True,
        error=None,
    )
