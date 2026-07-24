"""Canonical merge for V3.6 source snapshots."""
from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

_SPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^a-z0-9æøå]+", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[a-z0-9æøå]+", re.IGNORECASE)


def _normalized_text(value: object) -> str:
    text = _SPACE_RE.sub(" ", str(value or "").strip().lower())
    return _NON_WORD_RE.sub("", text)


def _normalized_tokens(value: object) -> tuple[str, ...]:
    return tuple(token.lower() for token in _TOKEN_RE.findall(str(value or "")))


def _price_value(source: dict[str, Any]) -> int | None:
    value = source.get("asking_price_nok")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return int(round(float(value)))
    return None


def canonical_duplicate_key(opportunity: dict[str, Any]) -> str:
    source = opportunity.get("source") if isinstance(opportunity.get("source"), dict) else {}
    title = _normalized_text(source.get("title"))
    location = _normalized_text(source.get("location"))
    price = _price_value(source)
    price_text = f"{price:.2f}" if price is not None else ""
    material = "|".join((title, location, price_text))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _locations_compatible(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_location = _normalized_text(left.get("location"))
    right_location = _normalized_text(right.get("location"))
    return not left_location or not right_location or left_location == right_location


def _model_price_contamination_match(
    short_source: dict[str, Any],
    long_source: dict[str, Any],
) -> bool:
    """Recognize a model number accidentally consumed as the start of a price.

    Example: ``BerryAlloc Route 66 10 000 kr`` may be parsed by an older source
    adapter as title ``BerryAlloc Route`` and price ``6610000``.  A second source
    carrying title ``BerryAlloc Route 66`` and price ``10000`` provides enough
    evidence to recover identity for deduplication only.  No financial value is
    rewritten or persisted here.
    """

    short_tokens = _normalized_tokens(short_source.get("title"))
    long_tokens = _normalized_tokens(long_source.get("title"))
    if len(short_tokens) < 2 or len(long_tokens) != len(short_tokens) + 1:
        return False
    if long_tokens[:-1] != short_tokens:
        return False

    model_token = long_tokens[-1]
    if not model_token.isdigit():
        return False

    contaminated_price = _price_value(short_source)
    clean_price = _price_value(long_source)
    if contaminated_price is None or clean_price is None:
        return False

    return str(contaminated_price) == f"{model_token}{clean_price}"


def _same_listing(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_source = left.get("source") if isinstance(left.get("source"), dict) else {}
    right_source = right.get("source") if isinstance(right.get("source"), dict) else {}

    if not _locations_compatible(left_source, right_source):
        return False

    left_title = _normalized_text(left_source.get("title"))
    right_title = _normalized_text(right_source.get("title"))
    left_price = _price_value(left_source)
    right_price = _price_value(right_source)

    if left_title and left_title == right_title and left_price is not None and left_price == right_price:
        return True

    return _model_price_contamination_match(left_source, right_source) or _model_price_contamination_match(
        right_source, left_source
    )


def merge_snapshots(snapshots: Iterable[dict[str, Any]]) -> dict[str, Any]:
    snapshot_list = list(snapshots)
    merged: list[dict[str, Any]] = []
    duplicates: list[dict[str, str]] = []
    sources: list[str] = []
    captured_at = None

    for snapshot in snapshot_list:
        source_name = str(snapshot.get("source") or "").strip()
        if source_name and source_name not in sources:
            sources.append(source_name)
        captured_at = captured_at or snapshot.get("captured_at")
        opportunities = snapshot.get("opportunities")
        for item in opportunities if isinstance(opportunities, list) else []:
            if not isinstance(item, dict):
                continue
            opportunity_id = str(item.get("opportunity_id") or "")
            canonical_item = next((existing for existing in merged if _same_listing(existing, item)), None)
            if canonical_item is not None:
                duplicates.append({
                    "duplicate_opportunity_id": opportunity_id,
                    "canonical_opportunity_id": str(canonical_item.get("opportunity_id") or ""),
                })
                continue
            merged.append(item)

    return {
        "schema_version": "3.6",
        "captured_at": captured_at,
        "sources": sources,
        "source_count": len(sources),
        "opportunities_received": sum(
            len(s.get("opportunities") or []) for s in snapshot_list if isinstance(s.get("opportunities"), list)
        ),
        "opportunities": merged,
        "unique_opportunities": len(merged),
        "duplicate_count": len(duplicates),
        "duplicates": duplicates,
        "automatic_purchase_decision": False,
    }
