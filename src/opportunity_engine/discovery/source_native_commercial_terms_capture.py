"""Conservative source-native commercial-term capture from already-fetched pages.

This module records explicit condition, seller-identity, and fulfilment snippets
from source text. It does not interpret, normalize, qualify, rank, contact, bid,
or purchase. Captured snippets remain evidence-only and may be ambiguous.
"""
from __future__ import annotations

import re
from typing import Pattern

CAPTURE_VERSION = "SOURCE_NATIVE_COMMERCIAL_TERMS_CAPTURE_V1"
MAX_CANDIDATES_PER_FIELD = 8

_CONDITION_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(
        r"\b(?:skick|condition|zustand|état|etat|condizione|staat|tilstand)\b"
        r"\s*[:=\-]\s*[^\n\r|;.!?]{1,120}",
        re.IGNORECASE,
    ),
)

_SELLER_IDENTITY_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(
        r"\b(?:säljare|saljare|seller|verkäufer|verkaufer|vendeur|venditore|"
        r"verkoper|företag|foretag|company|bolag)\b\s*[:=\-]\s*"
        r"[^\n\r|;.!?]{2,120}",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:organisationsnummer|organisationsnr|org\.?\s*nr|orgnr|company\s+number)\b"
        r"\s*[:=\-]?\s*[A-Z0-9][A-Z0-9\- ]{4,24}",
        re.IGNORECASE,
    ),
)

_FULFILMENT_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(
        r"\b(?:frakt|leverans|shipping|delivery|versand|abholung|avhämtning|"
        r"avhamtning|hämtning|hamtning|pickup)\b\s*[:=\-]\s*"
        r"[^\n\r|;.!?]{1,140}",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:endast\s+avhämtning|endast\s+avhamtning|hämtas\s+på\s+plats|"
        r"hamtas\s+pa\s+plats|pickup\s+only|collection\s+only|shipping\s+available|"
        r"frakt\s+tillkommer|leverans\s+möjlig|leverans\s+mojlig)\b"
        r"[^\n\r|;.!?]{0,100}",
        re.IGNORECASE,
    ),
)


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _bounded_matches(text: str, patterns: tuple[Pattern[str], ...]) -> list[str]:
    ordered: list[tuple[int, str]] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            value = _compact(match.group(0))
            if value:
                ordered.append((match.start(), value))
    ordered.sort(key=lambda item: item[0])

    values: list[str] = []
    seen: set[str] = set()
    for _, value in ordered:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        values.append(value)
        if len(values) >= MAX_CANDIDATES_PER_FIELD:
            break
    return values


def capture_source_native_commercial_terms(text: str) -> dict[str, object]:
    """Capture explicit source-native commercial snippets without interpretation."""
    source_text = str(text or "")
    return {
        "version": CAPTURE_VERSION,
        "condition_candidates": _bounded_matches(source_text, _CONDITION_PATTERNS),
        "seller_identity_candidates": _bounded_matches(
            source_text, _SELLER_IDENTITY_PATTERNS
        ),
        "fulfilment_candidates": _bounded_matches(source_text, _FULFILMENT_PATTERNS),
        "capture_is_qualification_evidence": False,
        "financial_analysis_ready": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
