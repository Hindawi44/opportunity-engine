"""Taxonomy-aware fail-closed page verification policy for Norway textiles.

The existing page verifier remains responsible for fetching and parsing public
pages. This module only decides whether a verified page may continue toward
ranking. It preserves the current page-role, lifecycle, identity, and evidence
requirements while allowing every supported textile taxonomy category.
"""
from __future__ import annotations

from dataclasses import dataclass

from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    ITEM_LISTING,
    PageVerification,
)
from opportunity_engine.discovery.textile_taxonomy import OpportunityCategory


@dataclass(frozen=True, slots=True)
class TextilePageVerificationDecision:
    accepted: bool
    reason: str
    category: str


_SUPPORTED_CATEGORIES = frozenset(category.value for category in OpportunityCategory)


def evaluate_norway_textile_page_verification(
    verification: PageVerification,
    *,
    category: str,
) -> TextilePageVerificationDecision:
    """Apply the strict post-fetch gate without inferring missing evidence."""
    if category not in _SUPPORTED_CATEGORIES:
        return TextilePageVerificationDecision(
            False,
            "unsupported textile taxonomy category",
            category,
        )
    if not verification.verified:
        return TextilePageVerificationDecision(
            False,
            verification.error or "public page was not verified",
            category,
        )
    if verification.page_role != ITEM_LISTING:
        return TextilePageVerificationDecision(
            False,
            "verified page is not a specific item listing",
            category,
        )
    if verification.listing_status != ACTIVE:
        return TextilePageVerificationDecision(
            False,
            "listing is not verified active",
            category,
        )
    if not verification.identity_stable or not verification.opportunity_identity:
        return TextilePageVerificationDecision(
            False,
            "listing identity is not stable",
            category,
        )
    if not verification.clothing_inventory_evidence:
        return TextilePageVerificationDecision(
            False,
            "verified page lacks textile or sewing asset evidence",
            category,
        )
    if not verification.sale_evidence:
        return TextilePageVerificationDecision(
            False,
            "verified page lacks public sale evidence",
            category,
        )
    return TextilePageVerificationDecision(
        True,
        "active specific textile listing passed strict page verification",
        category,
    )


NORWAY_TEXTILE_PAGE_VERIFICATION_CATEGORIES = _SUPPORTED_CATEGORIES
