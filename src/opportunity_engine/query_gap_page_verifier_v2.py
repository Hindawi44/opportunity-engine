"""Conservative V2 verifier for official closure/inventory pages.

V2 is additive: the legacy verifier remains authoritative whenever it already
accepts a page. The extension recognizes a small set of formal closure phrases
seen on official company pages (for example ``avvikler virksomheten``), while
preserving every stock-safety requirement: exact HTTPS HTML, no temporary
closure, a sale term, inventory-liquidation evidence, and a concrete company
identity.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from opportunity_engine.automatic_query_gap_miss_scout import (
    PublicPage,
    _CLOSURE_MARKERS,
    _GAP_TERMS,
    _LIQUIDATION_MARKERS,
    _TEMPORARY_MARKERS,
    _bounded_context,
    _canonical,
    _extract_company,
    _verify_closure_liquidation_page,
    _visible_text,
)

EXTENDED_CLOSURE_MARKERS = tuple(
    dict.fromkeys(
        (
            *_CLOSURE_MARKERS,
            "avvikler virksomheten",
            "avvikler driften",
            "innstiller driften",
            "stenger dørene for godt",
            "avslutter virksomheten",
        )
    )
)
EXTENDED_LIQUIDATION_MARKERS = tuple(
    dict.fromkeys(
        (
            *_LIQUIDATION_MARKERS,
            "selge ut vårt sortiment",
            "selger ut vårt sortiment",
            "selge ut sortimentet",
            "selger ut sortimentet",
            "selge ut hele sortimentet",
            "selger ut hele sortimentet",
        )
    )
)

_EXTENDED_COMPANY_PATTERN = re.compile(
    r"\b([A-ZÆØÅ][A-Za-zÆØÅæøå0-9&.'’\-]{1,79})\s+"
    r"(?i:avvikler virksomheten|avvikler driften|innstiller driften|"
    r"stenger dørene for godt|avslutter virksomheten)\b"
)
_GENERIC_EXTENDED_COMPANY_LABELS = frozenset({"vi", "butikken", "bedriften", "selskapet"})


def _extended_company(text: str) -> str | None:
    legacy = _extract_company(text)
    if legacy:
        return legacy
    for match in _EXTENDED_COMPANY_PATTERN.finditer(text):
        value = " ".join(match.group(1).split()).strip(" -–—|:,.;")
        if value and value.casefold() not in _GENERIC_EXTENDED_COMPANY_LABELS:
            return value
    return None


def page_evidence_v2(page: PublicPage) -> dict[str, Any]:
    """Return read-only evidence dimensions used by V2 verification."""
    final = _canonical(page.final_url)
    html_ok = page.status_code == 200 and "text/html" in page.content_type.casefold()
    https_ok = bool(final and urlparse(final).scheme == "https")
    text = _visible_text(page.html) if html_ok else ""
    folded = text.casefold()

    temporary_markers = [marker for marker in _TEMPORARY_MARKERS if marker in folded]
    closure_markers = [marker for marker in EXTENDED_CLOSURE_MARKERS if marker in folded]
    sale_terms = [term for term in _GAP_TERMS if term in folded]
    liquidation_markers = [
        marker for marker in EXTENDED_LIQUIDATION_MARKERS if marker in folded
    ]
    company = _extended_company(text) if text else None

    return {
        "canonical_url": final,
        "text": text,
        "http_status_ok": page.status_code == 200,
        "html_ok": html_ok,
        "https_ok": https_ok,
        "temporary_markers": temporary_markers,
        "closure_markers": closure_markers,
        "sale_terms": sale_terms,
        "liquidation_markers": liquidation_markers,
        "company": company,
    }


def verify_query_gap_page_v2(page: PublicPage) -> dict[str, Any] | None:
    """Verify exact public evidence without weakening the legacy stock gate."""
    legacy = _verify_closure_liquidation_page(page)
    if legacy is not None:
        return legacy

    evidence = page_evidence_v2(page)
    final = str(evidence["canonical_url"] or "")
    text = str(evidence["text"] or "")
    if not evidence["http_status_ok"] or not evidence["html_ok"] or not evidence["https_ok"]:
        return None
    if not final or not text or evidence["temporary_markers"]:
        return None
    if not evidence["closure_markers"]:
        return None
    if not evidence["sale_terms"]:
        return None
    if not evidence["liquidation_markers"]:
        return None
    if not evidence["company"]:
        return None

    sale_terms = list(evidence["sale_terms"])
    return {
        "canonical_url": final,
        "company": str(evidence["company"]),
        "query_gap_terms": sale_terms,
        "closure_markers": list(evidence["closure_markers"]),
        "liquidation_markers": list(evidence["liquidation_markers"]),
        "evidence_text": _bounded_context(text, sale_terms[0]),
        "source_page_verified": True,
        "closure_verified": True,
        "inventory_liquidation_verified": True,
        "verifier_version": "V2_CONSERVATIVE_EXTENSION",
    }
