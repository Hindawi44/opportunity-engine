"""Canonical market-price evidence contract for Opportunity Engine V2.8.2B.

Every external comparable must pass through ``candidate_to_market_price_evidence``
before it can be persisted. The contract deliberately rejects incomplete, placeholder,
non-public, non-NOK, or non-positive price evidence.
"""
from __future__ import annotations

from ipaddress import ip_address
from math import isfinite
from typing import Any
from urllib.parse import urlparse

from opportunity_engine.evidence_store import (
    EvidenceConfidence,
    EvidenceDirection,
    EvidenceType,
    ResearchEvidence,
)


_PLACEHOLDER_HOSTS = {
    "example.com",
    "example.net",
    "example.org",
    "unknown.no",
    "localhost",
}


def _read(candidate: Any, name: str, default: Any = None) -> Any:
    if isinstance(candidate, dict):
        return candidate.get(name, default)
    return getattr(candidate, name, default)


def _public_https_url(value: Any) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    host = (parsed.hostname or "").strip().casefold().rstrip(".")
    if parsed.scheme.casefold() != "https" or not host:
        raise ValueError("comparable source_url must be a public HTTPS URL")
    if parsed.username or parsed.password:
        raise ValueError("comparable source_url must not contain credentials")
    if host in _PLACEHOLDER_HOSTS or host.endswith(".invalid") or host.endswith(".local"):
        raise ValueError("comparable source_url cannot be placeholder or local")
    try:
        address = ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("comparable source_url must resolve to a public host")
    return url


def _positive_nok_price(candidate: Any) -> float:
    currency = str(_read(candidate, "currency", _read(candidate, "price_currency", "NOK")) or "").strip().upper()
    if currency != "NOK":
        raise ValueError("comparable price currency must be NOK")
    raw = _read(candidate, "price_nok", _read(candidate, "numeric_value"))
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError("comparable price must be an explicit numeric value")
    price = float(raw)
    if not isfinite(price) or price <= 0:
        raise ValueError("comparable price must be positive")
    return price


def _validated_similarity(candidate: Any) -> float:
    raw = _read(candidate, "similarity_score")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError("similarity_score must be explicitly calculated before evidence conversion")
    value = float(raw)
    if not isfinite(value) or not 0 <= value <= 1:
        raise ValueError("similarity_score must be between 0 and 1")
    return value


def candidate_to_market_price_evidence(candidate: Any, opportunity_id: str) -> ResearchEvidence:
    """Convert one validated comparable candidate into canonical persisted evidence.

    No caller may manufacture ``market_price`` evidence directly. The candidate must
    already contain an explicitly calculated similarity score; this function never
    supplies a guessed default.
    """
    normalized_opportunity_id = str(opportunity_id or "").strip()
    if not normalized_opportunity_id:
        raise ValueError("opportunity_id cannot be empty")

    title = str(_read(candidate, "title") or "").strip()
    if not title:
        raise ValueError("comparable title cannot be empty")
    source_url = _public_https_url(_read(candidate, "url", _read(candidate, "source_url")))
    price = _positive_nok_price(candidate)
    similarity = _validated_similarity(candidate)
    source_name = str(_read(candidate, "source_name") or "external_market_comparable").strip()
    observed_at = str(_read(candidate, "observed_at") or "").strip() or None

    statement = f"Verified external market comparable: {title} — {price:.2f} NOK."
    return ResearchEvidence.create(
        opportunity_id=normalized_opportunity_id,
        evidence_type=EvidenceType.MARKET_PRICE,
        statement=statement,
        source_name=source_name,
        source_url=source_url,
        confidence=EvidenceConfidence.MEDIUM,
        direction=EvidenceDirection.NEUTRAL,
        numeric_value=price,
        currency="NOK",
        notes=f"observed_at:{observed_at}" if observed_at else None,
        metadata={
            "external": True,
            "contract_version": "2.8.2B",
            "similarity_score": similarity,
            "candidate_title": title,
        },
    )
