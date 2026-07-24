"""Persistent lifecycle state for opportunities across source snapshots.

V3.4 compares raw snapshots only. It does not search, score, infer missing values,
or modify any V2.8-V3.3 contract.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
from typing import Any, Iterable

_TRACKED_FIELDS = (
    "title",
    "description",
    "location",
    "auction_price_nok",
    "listing_status",
    "url",
)


def stable_opportunity_id(record: dict[str, Any]) -> str:
    listing_id = str(record.get("listing_id") or "").strip()
    source = str(record.get("source_name") or record.get("source") or "unknown").strip().lower()
    if listing_id:
        return f"{source}:{listing_id}"
    url = str(record.get("url") or record.get("source_url") or "").strip()
    if not url:
        raise ValueError("opportunity requires listing_id or source URL")
    digest = sha256(url.encode("utf-8")).hexdigest()[:20]
    return f"{source}:url:{digest}"


def _business_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {field: record.get(field) for field in _TRACKED_FIELDS}


def _fingerprint(record: dict[str, Any]) -> str:
    payload = repr(sorted(_business_payload(record).items()))
    return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class LifecycleEvent:
    opportunity_id: str
    lifecycle_status: str
    changed_fields: tuple[str, ...]
    observed_at: str | None
    record: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["changed_fields"] = list(self.changed_fields)
        return data


def normalize_lifecycle_state(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    records = payload.get("records")
    return {
        "schema_version": "3.4",
        "records": records if isinstance(records, dict) else {},
    }


def compare_snapshot(
    opportunities: Iterable[dict[str, Any]],
    previous_state: dict[str, Any] | None = None,
    *,
    observed_at: str | None = None,
    archive_after_missing_runs: int = 2,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if archive_after_missing_runs < 1:
        raise ValueError("archive_after_missing_runs must be positive")

    state = normalize_lifecycle_state(previous_state)
    old_records: dict[str, Any] = state["records"]
    next_records: dict[str, Any] = {}
    events: list[LifecycleEvent] = []
    seen_ids: set[str] = set()

    for record in opportunities:
        if not isinstance(record, dict):
            continue
        opportunity_id = stable_opportunity_id(record)
        if opportunity_id in seen_ids:
            continue
        seen_ids.add(opportunity_id)
        current_fp = _fingerprint(record)
        previous = old_records.get(opportunity_id)
        if not isinstance(previous, dict):
            status = "NEW"
            changed = tuple(_TRACKED_FIELDS)
        elif previous.get("fingerprint") != current_fp:
            old_payload = previous.get("payload") if isinstance(previous.get("payload"), dict) else {}
            new_payload = _business_payload(record)
            changed = tuple(field for field in _TRACKED_FIELDS if old_payload.get(field) != new_payload.get(field))
            status = "UPDATED"
        else:
            status = "UNCHANGED"
            changed = ()

        next_records[opportunity_id] = {
            "opportunity_id": opportunity_id,
            "fingerprint": current_fp,
            "payload": _business_payload(record),
            "record": record,
            "first_seen_at": previous.get("first_seen_at") if isinstance(previous, dict) else observed_at,
            "last_seen_at": observed_at,
            "missing_runs": 0,
            "lifecycle_status": status,
        }
        events.append(LifecycleEvent(opportunity_id, status, changed, observed_at, record))

    for opportunity_id, previous in old_records.items():
        if opportunity_id in seen_ids or not isinstance(previous, dict):
            continue
        missing_runs = int(previous.get("missing_runs") or 0) + 1
        status = "ARCHIVED" if missing_runs >= archive_after_missing_runs else "REMOVED"
        retained = dict(previous)
        retained.update({
            "missing_runs": missing_runs,
            "lifecycle_status": status,
            "last_seen_at": previous.get("last_seen_at"),
        })
        next_records[opportunity_id] = retained
        events.append(LifecycleEvent(opportunity_id, status, (), observed_at, previous.get("record")))

    next_state = {
        "schema_version": "3.4",
        "updated_at": observed_at,
        "records": next_records,
    }
    return [event.to_dict() for event in events], next_state


def actionable_records(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        event["record"]
        for event in events
        if event.get("lifecycle_status") in {"NEW", "UPDATED"}
        and isinstance(event.get("record"), dict)
    ]
