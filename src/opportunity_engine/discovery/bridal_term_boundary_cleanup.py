"""Prevent embedded-word matches from contaminating bridal market signals.

The bridal feeds intentionally use compact term packs across Norwegian, Swedish,
German, and English. Raw substring matching can turn unrelated larger words into
commercial evidence (for example ``stock`` inside ``Stockholm`` or ``lager``
inside ``Lagerström``). This compatibility hook keeps the existing term packs and
query budgets intact while requiring each configured term or phrase to occur on
Unicode word boundaries.
"""
from __future__ import annotations

import re
from typing import Sequence

from opportunity_engine.discovery import bridal_english_market_search as english_feed
from opportunity_engine.discovery import bridal_liquidation_feed as local_feed

PATCH_SCHEMA_VERSION = "bridal-term-boundary-cleanup-1.0"
_INSTALLED = False


def boundary_aware_matched_terms(text: str, terms: Sequence[str]) -> list[str]:
    """Return configured terms only when they occur as complete words/phrases."""
    folded = local_feed._compact(text).casefold()
    matched: list[str] = []
    for term in terms:
        needle = local_feed._compact(term).casefold()
        if not needle:
            continue
        pattern = rf"(?<!\w){re.escape(needle)}(?!\w)"
        if re.search(pattern, folded, flags=re.UNICODE):
            matched.append(term)
    return matched


def install_bridal_term_boundary_cleanup() -> None:
    """Install the same precision matcher in the local and English bridal lanes."""
    global _INSTALLED
    if _INSTALLED:
        return
    local_feed._matched_terms = boundary_aware_matched_terms
    english_feed._matched_terms = boundary_aware_matched_terms
    local_feed.BRIDAL_TERM_MATCH_PATCH_SCHEMA_VERSION = PATCH_SCHEMA_VERSION
    english_feed.BRIDAL_TERM_MATCH_PATCH_SCHEMA_VERSION = PATCH_SCHEMA_VERSION
    _INSTALLED = True
