"""Canonical merge for V3.6 source snapshots."""
from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

_SPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^a-z0-9æøå]+", re.IGNORECASE)


def _normalized_text(value: object) -> str:
    text = _SPACE_RE.sub(" ", str(value or "").strip().lower())
    return _NON_WORD_RE.sub("", text)


def canonical_duplicate_key(opportunity: dict[str, Any]) -> str:
    source = opportunity.get("source") if isinstance(opportunity.get("source"), dict) else {}
    title = _normalized_text(source.get("title"))
    location = _normalized_text(source.get("location"))
    price = source.get("asking_price_nok")
    price_text = f"{float(price):.2f}" if isinstance(price, (int, float)) and not isinstance(price, bool) else ""
    material = "|".join((title, location, price_text))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def merge_snapshots(snapshots: Iterable[dict[str, Any]]) -> dict[str, Any]:
    snapshot_list = list(snapshots)
    merged: list[dict[str, Any]] = []
    duplicates: list[dict[str, str]] = []
    seen: dict[str, str] = {}
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
            key = canonical_duplicate_key(item)
            opportunity_id = str(item.get("opportunity_id") or "")
            if key in seen:
                duplicates.append({
                    "duplicate_opportunity_id": opportunity_id,
                    "canonical_opportunity_id": seen[key],
                })
                continue
            seen[key] = opportunity_id
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
