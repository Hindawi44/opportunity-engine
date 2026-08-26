"""General parser recovery for direct Exact-Lot pages already found by search.

This patch is deliberately source-neutral and budget-neutral. It fixes
conservative evidence-parsing gaps observed in live six-market runs:

* European prices written as ``306,50 €`` were not detected by the direct-page
  price regex because the old expression required a word boundary after ``€``.
* Some B2B marketplaces expose a descriptive lot slug followed by a stable
  numeric record id, for example ``.../restpartij-...-76-stuks/37463``.
* Other marketplaces encode the same stable record id at the end of a descriptive
  HTML detail slug, for example ``.../mixposten-textilien-16083444.html``.
* Some listing platforms expose a concrete item as ``/listing/<descriptive-lot-slug>``
  without a numeric id. That route is accepted only when the slug itself is
  multi-token and proves explicit lot/bulk intent.

The descriptive slug must still prove explicit lot/bulk intent. Bare category,
search, blog and generic year/id routes remain aggregate or non-item-specific.
The recovery changes URL/price evidence only. CLOTHING_INVENTORY, inventory,
direct-sale, price, quantity and all existing Exact-Lot gates remain required.
No search request, page fetch, provider, source, runtime, market or commercial
action is added.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from opportunity_engine.discovery import exa_shadow_page_verification as _verification


VERSION = "DIRECT_EXACT_LOT_PARSER_RECOVERY_V1_2"

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
_HTML_RECORD_SLUG_RE = re.compile(
    r"^(?P<slug>.+)-(?P<record_id>\d{5,})\.html?$",
    re.IGNORECASE,
)
_UNIT_QUANTITY_TOKEN_RE = re.compile(
    r"^\d{2,}(?:kg|stk|stuks|pcs|pieces|pièces|pezzi|units)$",
    re.IGNORECASE,
)
_RECOVERY_LOT_PREFIXES = (
    "varepart",
    "lagerpart",
)

_UPSTREAM_LOOKS_ITEM_SPECIFIC_URL = _verification._looks_item_specific_url
_INSTALLED = False


def _slug_tokens(slug: str) -> list[str]:
    return [
        token
        for token in re.split(r"[-_]+", _verification._compact(slug).casefold())
        if token
    ]


def _slug_has_explicit_lot_intent(slug: str) -> bool:
    """Require explicit lot/bulk language, not a bare number such as a year."""
    tokens = _slug_tokens(slug)
    if any(token in _verification._LOCAL_LOT_PRODUCT_TERMS for token in tokens):
        return True
    if any(
        token.startswith(prefix)
        for token in tokens
        for prefix in _verification._LOCAL_LOT_PRODUCT_PREFIXES
    ):
        return True
    if any(token.startswith(prefix) for token in tokens for prefix in _RECOVERY_LOT_PREFIXES):
        return True
    return any(_UNIT_QUANTITY_TOKEN_RE.fullmatch(token) for token in tokens)


def _looks_item_specific_url_v2(url: str) -> bool:
    """Extend specificity only for conservative lot-intent detail URL shapes."""
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
    if not segments:
        return False

    # Shape A: .../<descriptive-lot-slug>/<numeric-record-id>
    if len(segments) >= 2 and _NUMERIC_RECORD_ID_RE.fullmatch(segments[-1]):
        return _slug_has_explicit_lot_intent(segments[-2])

    # Shape B: .../<descriptive-lot-slug>-<numeric-record-id>.html
    html_match = _HTML_RECORD_SLUG_RE.fullmatch(segments[-1])
    if html_match:
        return _slug_has_explicit_lot_intent(html_match.group("slug"))

    # Shape C: .../listing/<descriptive-lot-slug>
    # Require a multi-token descriptive slug so bare collection labels such as
    # /listing/klaer or /listing/vareparti cannot become item-specific merely
    # because they sit below a listing container.
    if len(segments) >= 2 and segments[-2] == "listing":
        slug = segments[-1]
        tokens = _slug_tokens(slug)
        if len(tokens) >= 3 and "-" in slug and _slug_has_explicit_lot_intent(slug):
            return True

    return False


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
