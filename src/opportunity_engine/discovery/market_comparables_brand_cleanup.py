"""Prevent generic lot descriptors from becoming market-comparable brands.

Market-comparable hydration historically treated any capitalised title token as a
possible brand. Sentence-initial quantity/lot descriptors such as ``Halv`` in
``Halv pall med Bauer jakker`` could therefore contaminate both the inferred
brand list and the benchmark search query. This compatibility hook preserves the
existing hydration implementation and only extends its deterministic noise sets.
"""
from __future__ import annotations

from opportunity_engine.discovery import market_comparables_target_hydration as target

PATCH_SCHEMA_VERSION = "market-comparables-brand-cleanup-1.0"
_INSTALLED = False

# Generic quantity / lot wording, not product brands. Keep this deliberately
# narrow: these tokens describe the container or amount and are safe to exclude
# from both brand inference and comparable-search query terms.
_LOT_DESCRIPTOR_TOKENS = {
    "halv",
    "hel",
    "half",
    "full",
    "pall",
    "pallet",
    "parti",
    "pakke",
    "batch",
    "lot",
    "restparti",
    "lagerparti",
}


def install_market_comparables_brand_cleanup() -> None:
    """Install deterministic descriptor guards without changing source truth."""
    global _INSTALLED
    if _INSTALLED:
        return
    target._GENERIC_COMPANY_TOKENS.update(_LOT_DESCRIPTOR_TOKENS)
    target._QUERY_NOISE.update(_LOT_DESCRIPTOR_TOKENS)
    _INSTALLED = True
