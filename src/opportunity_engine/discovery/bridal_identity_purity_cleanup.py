"""Keep generic showroom/sample descriptors from establishing bridal identity.

Recent live Bridal discovery exposed a precision gap that term boundaries alone do
not solve: generic inventory words such as Swedish ``butiksexemplar`` or German
``Ausstellungsstücke`` can describe any retail category. They are useful batch or
surplus evidence only after independent bridal identity is already present, but
must never be sufficient to label a result as BRIDAL by themselves.
"""
from __future__ import annotations

from opportunity_engine.discovery import bridal_liquidation_feed as local_feed

PATCH_SCHEMA_VERSION = "bridal-identity-purity-cleanup-1.0"
_INSTALLED = False

_GENERIC_NON_BRIDAL_IDENTITY_TERMS: dict[str, frozenset[str]] = {
    "SE": frozenset({"butiksexemplar"}),
    "DE": frozenset({"ausstellungsstücke", "ausstellungsstucke"}),
}


def install_bridal_identity_purity_cleanup() -> None:
    """Require explicit bridal vocabulary before generic stock/sample evidence counts."""
    global _INSTALLED
    if _INSTALLED:
        return

    for market, generic_terms in _GENERIC_NON_BRIDAL_IDENTITY_TERMS.items():
        local_feed._BRIDAL_TERMS[market] = tuple(
            term
            for term in local_feed._BRIDAL_TERMS[market]
            if term.casefold() not in {item.casefold() for item in generic_terms}
        )

    local_feed.BRIDAL_IDENTITY_PURITY_PATCH_SCHEMA_VERSION = PATCH_SCHEMA_VERSION
    _INSTALLED = True
