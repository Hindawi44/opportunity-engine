"""Persistent, conservative aggregation of verified external market comparables."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class ComparableSummary:
    opportunity_id: str
    verified_comparables: tuple[dict[str, Any], ...]
    comparable_status: str
    independent_domains: int
    duplicate_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "verified_comparable_count": len(self.verified_comparables),
            "verified_comparables": list(self.verified_comparables),
            "comparable_status": self.comparable_status,
            "independent_domains": self.independent_domains,
            "duplicate_count": self.duplicate_count,
        }


def _canonical_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}"


def _domain(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def _records(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    nested = payload.get("evidence", payload.get("records"))
    if isinstance(nested, list):
        return [item for item in nested if isinstance(item, dict)]
    return [payload] if payload.get("opportunity_id") else []


def collect_persisted_comparables(root: str | Path, *, target_count: int = 3) -> dict[str, ComparableSummary]:
    """Collect explicit NOK market-price evidence recursively and deduplicate it.

    A comparable must have a positive NOK observation and a public HTTPS source. Results
    are accumulated across runs from ``data/evidence/<opportunity_id>/rev_*.json``.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    duplicates: dict[str, int] = {}
    seen: dict[str, set[tuple[str, float]]] = {}

    for path in sorted(Path(root).rglob("*.json")):
        for record in _records(path):
            opportunity_id = str(record.get("opportunity_id") or "").strip()
            if not opportunity_id or str(record.get("evidence_type") or "") != "market_price":
                continue
            url = str(record.get("source_url") or "").strip()
            if not url.startswith("https://") or not _domain(url):
                continue
            for observation in record.get("observations") or []:
                if not isinstance(observation, dict):
                    continue
                value = observation.get("numeric_value")
                currency = str(observation.get("currency") or "").upper()
                if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0 or currency != "NOK":
                    continue
                key = (_canonical_url(url), float(value))
                opportunity_seen = seen.setdefault(opportunity_id, set())
                if key in opportunity_seen:
                    duplicates[opportunity_id] = duplicates.get(opportunity_id, 0) + 1
                    continue
                opportunity_seen.add(key)
                metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
                grouped.setdefault(opportunity_id, []).append({
                    "evidence_id": record.get("evidence_id"),
                    "title": metadata.get("comparable_title"),
                    "source": record.get("source_name") or "external_market_comparable",
                    "url": url,
                    "domain": _domain(url),
                    "price_nok": float(value),
                    "similarity_score": metadata.get("similarity_score"),
                    "observed_at": observation.get("observed_at"),
                })

    result: dict[str, ComparableSummary] = {}
    for opportunity_id, items in grouped.items():
        items.sort(key=lambda item: (-float(item.get("similarity_score") or 0), float(item["price_nok"])))
        selected = tuple(items[:target_count])
        count = len(selected)
        status = "COMPLETE" if count >= target_count else "PARTIAL" if count else "NOT_FOUND"
        result[opportunity_id] = ComparableSummary(
            opportunity_id=opportunity_id,
            verified_comparables=selected,
            comparable_status=status,
            independent_domains=len({str(item["domain"]) for item in selected}),
            duplicate_count=duplicates.get(opportunity_id, 0),
        )
    return result
