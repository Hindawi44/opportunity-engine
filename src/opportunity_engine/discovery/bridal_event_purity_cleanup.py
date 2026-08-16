"""Require an actual commercial event, not only a bridal inventory descriptor.

The Bridal feed keeps product/inventory words such as sample dresses and showroom
pieces as identity or batch evidence. Those words must not also be sufficient to
classify a page as WAREHOUSE_SURPLUS by themselves; otherwise ordinary catalogue or
advice pages can become market-event signals without any sale, clearance, surplus,
or liquidation evidence.
"""
from __future__ import annotations

from opportunity_engine.discovery import bridal_liquidation_feed as local_feed

PATCH_SCHEMA_VERSION = "bridal-event-purity-cleanup-1.0"
_INSTALLED = False

_INVENTORY_ONLY_SURPLUS_TERMS: dict[str, frozenset[str]] = {
    "NO": frozenset({"prøvekjoler"}),
    "SE": frozenset({"provklänningar", "provklanningar", "butiksexemplar"}),
    "DE": frozenset(
        {
            "musterkleider",
            "ausstellungsstücke",
            "ausstellungsstucke",
        }
    ),
}


def install_bridal_event_purity_cleanup() -> None:
    """Keep inventory nouns as batch evidence, but not as event evidence."""
    global _INSTALLED
    if _INSTALLED:
        return

    for market, inventory_only_terms in _INVENTORY_ONLY_SURPLUS_TERMS.items():
        blocked = {item.casefold() for item in inventory_only_terms}
        local_feed._SURPLUS_TERMS[market] = tuple(
            term for term in local_feed._SURPLUS_TERMS[market] if term.casefold() not in blocked
        )

    local_feed.BRIDAL_EVENT_PURITY_PATCH_SCHEMA_VERSION = PATCH_SCHEMA_VERSION
    _INSTALLED = True
