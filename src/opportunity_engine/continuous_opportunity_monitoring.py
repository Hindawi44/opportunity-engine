"""V3.2 stateful monitoring over already-collected opportunity snapshots.

This module does not scrape sources, infer evidence, recalculate financial values, or
alter V2.8-V3.1 contracts. It fingerprints collected opportunities, detects unseen
records, and advances an explicit monitoring state.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Iterable


def _text(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def opportunity_fingerprint(opportunity: dict[str, Any]) -> str:
    """Return a deterministic identity for one collected opportunity.

    Stable source identifiers are preferred. When absent, the source URL, title,
    location and asking price form the canonical identity. Missing identity fields
    are rejected rather than producing a shared or synthetic fingerprint.
    """
    source = opportunity.get("source") if isinstance(opportunity.get("source"), dict) else {}
    stable_id = _text(source.get("listing_id") or opportunity.get("listing_id"))
    source_name = _text(source.get("name"))
    source_url = _text(source.get("url"))
    title = _text(source.get("title"))
    location = _text(source.get("location"))
    asking_price = source.get("asking_price_nok")

    if stable_id:
        identity = {"source": source_name, "listing_id": stable_id}
    else:
        if not source_url or not title:
            raise ValueError("opportunity requires listing_id or source URL and title")
        identity = {
            "source": source_name,
            "url": source_url,
            "title": title,
            "location": location,
            "asking_price_nok": asking_price,
        }
    canonical = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class MonitoringState:
    schema_version: str
    seen_fingerprints: tuple[str, ...]
    last_run_at: str | None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["seen_fingerprints"] = list(self.seen_fingerprints)
        return payload


def normalize_state(payload: object) -> MonitoringState:
    data = payload if isinstance(payload, dict) else {}
    seen = data.get("seen_fingerprints")
    seen_values = sorted({str(value) for value in seen if value}) if isinstance(seen, list) else []
    return MonitoringState(
        schema_version="3.2",
        seen_fingerprints=tuple(seen_values),
        last_run_at=str(data.get("last_run_at")) if data.get("last_run_at") else None,
    )


def detect_new_opportunities(
    opportunities: Iterable[dict[str, Any]],
    state: MonitoringState | dict[str, Any] | None = None,
    *,
    run_at: str | None = None,
) -> tuple[list[dict[str, Any]], MonitoringState, list[dict[str, Any]]]:
    """Return unseen opportunities, the advanced state, and rejected input records."""
    current = state if isinstance(state, MonitoringState) else normalize_state(state)
    seen = set(current.seen_fingerprints)
    new_records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for index, opportunity in enumerate(opportunities):
        if not isinstance(opportunity, dict):
            rejected.append({"index": index, "reason": "record is not an object"})
            continue
        try:
            fingerprint = opportunity_fingerprint(opportunity)
        except ValueError as exc:
            rejected.append({
                "index": index,
                "opportunity_id": opportunity.get("opportunity_id"),
                "reason": str(exc),
            })
            continue
        if fingerprint in seen:
            continue
        enriched = dict(opportunity)
        enriched["monitoring_fingerprint"] = fingerprint
        new_records.append(enriched)
        seen.add(fingerprint)

    next_state = MonitoringState(
        schema_version="3.2",
        seen_fingerprints=tuple(sorted(seen)),
        last_run_at=run_at or datetime.now(timezone.utc).isoformat(),
    )
    return new_records, next_state, rejected
