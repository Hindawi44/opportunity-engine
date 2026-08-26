"""General parser recovery for direct Exact-Lot pages already found by search.

This patch is deliberately source-neutral and budget-neutral. It fixes two
conservative evidence-parsing gaps observed in live six-market runs:

* European prices written as ``306,50 €`` were not detected by the direct-page
  price regex because the old expression required a word boundary after ``€``.
* Some B2B marketplaces expose a descriptive lot slug followed by a stable
  numeric record id, for example ``.../restpartij-...-76-stuks/37463``. The
  descriptive slug is strong URL-specificity evidence, while a bare category
  route such as ``.../kleding/43`` must remain aggregate.

The recovery changes URL/price evidence only. CLOTHING_INVENTORY, inventory,
direct-sale, price, quantity and all existing Exact-Lot gates remain required.
No search request, page fetch, provider, source, runtime, market or commercial
action is added.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from opportunity_engine.discovery import exa_shadow_page_verification as _verification


VERSION = "DIRECT_EXACT_LOT_PARSER_RECOVERY_V1"

# Preserve every old price form while fixing the symbol-suffix form. Word
# currencies retain a trailing word boundary; the non-word euro symbol does not.
_PRICE_RE_V2 = re.compile(
    r"(?:"
    r"\b\d[\d\s.,]{0,14}\s*(?:nok|sek|eur|euro|kr\.?)\b|"
    r"\b\d[\d\s.,]{0,14}\s*€|"
    r"(?:€|kr\.?)[\s]*\d"
    r")",
    re.IGNORECASE,
)
_NUMERIC_RECORD_ID_RE = re.compile(r"^\d{3,}$")

_UPSTREAM_LOOKS_ITEM_SPECIFIC_URL = _verification._looks_item_specific_url
_INSTALLED = False


def _looks_item_specific_url_v2(url: str) -> bool:
    """Extend URL specificity only for lot-intent slug + numeric record id."""
    if _UPSTREAM_LOOKS_ITEM_SPECIFIC_URL(url):
        return True

    try:
        parsed = urlsplit(_verification._compact(url))
    except ValueError:
        return False

    path = (parsed.path or "/").casefold().rstrip("/")
    if not path or path == "/":
        return False
    if any(marker in path for marker in _verification._AGGREGATE_PATH_MARKERS):
        return False

    segments = [segment for segment in path.strip("/").split("/") if segment]
    if len(segments) < 2 or not _NUMERIC_RECORD_ID_RE.fullmatch(segments[-1]):
        return False

    descriptive_slug = segments[-2]
    return _verification._product_slug_has_local_lot_intent(descriptive_slug)


def install_direct_exact_lot_parser_recovery_v1() -> None:
    """Install the bounded parser fix once, without altering search budgets."""
    global _INSTALLED
    if _INSTALLED:
        return
    _verification._PRICE_RE = _PRICE_RE_V2
    _verification._looks_item_specific_url = _looks_item_specific_url_v2
    _INSTALLED = True


__all__ = [
    "VERSION",
    "install_direct_exact_lot_parser_recovery_v1",
]
