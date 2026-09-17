"""Reconcile the review inbox with dated, source-native Auksjonen API evidence.

A listing absent from a bounded source scan is NOT necessarily ended. An
INPROGRESS result is NOT confirmation of stock or of an independently read page.
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlsplit


_ENDED = frozenset({"ENDED", "FINISHED", "SOLD", "CLOSED", "COMPLETED"})
_OPEN = frozenset({"INPROGRESS", "ACTIVE", "OPEN"})


def _time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None
    except ValueError:
        return None


def _key(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower()
    if (parsed.scheme not in {"http", "https"} or
            (host != "auksjonen.no" and not host.endswith(".auksjonen.no")) or
            not parsed.path.startswith("/auksjon/") or parsed.username or parsed.password):
        return None
    return host + parsed.path.rstrip("/").lower()


def reconcile_auksjonen_snapshot(queue: dict, snapshot: dict) -> dict:
    """Attach dated source evidence without treating a crawl as stock proof.

    The source API's explicit ended status moves a record to technical held,
    never to operator DELETE. Unknown or missing source entries remain uncertain.
    """
    counts = queue["counts"]
    captured = _time(snapshot.get("captured_at"))
    report_time = _time(queue.get("capture_timestamp"))
    listings = snapshot.get("listings")
    if (not str(snapshot.get("schema_version", "")).startswith("auksjonen-live-clothing-")
            or captured is None or not isinstance(listings, list)
            or (report_time is not None and captured > report_time)):
        counts["auksjonen_snapshot_status"] = "INVALID_OR_NEWER_THAN_REPORT"
        return queue
    index: dict[str, dict] = {}
    for item in listings:
        if not isinstance(item, dict) or item.get("source") != "Auksjonen Public API":
            continue
        key = _key(item.get("url"))
        if key and key not in index:
            index[key] = item

    scanned = ended = conflicts = missing = 0
    kept = []
    for row in queue["review_queue"]:
        key = _key(row.get("source_url"))
        if not key:
            kept.append(row)
            continue
        item = index.get(key)
        if item is None:
            row["source_status_note"] = "NOT_IN_BOUNDED_API_SNAPSHOT; no closure inferred"
            missing += 1
            kept.append(row)
            continue
        scanned += 1
        source_status = str(item.get("status") or "").upper()
        ends_at = _time(item.get("ends_at"))
        row["source_status_evidence"] = {
            "source": "Auksjonen Public API",
            "captured_at": captured.isoformat(),
            "status": source_status,
            "listing_status": item.get("listing_status"),
            "ends_at": item.get("ends_at"),
            "source_url": item["url"],
        }
        if source_status in _ENDED or str(item.get("listing_status") or "").upper() == "ENDED":
            row["stock_confidence"] = "SOURCE_REPORTED_ENDED_AT_CAPTURE"
            queue["held_separately"].append({
                "identity": row["identity"], "title": row["title"],
                "url": row["source_url"], "reason": "SOURCE_REPORTED_ENDED_NOT_OPERATOR_DELETE",
                "source_status_evidence": row["source_status_evidence"],
            })
            ended += 1
            continue
        if source_status in _OPEN and ends_at and ends_at <= captured:
            row["source_status_note"] = "END_TIME_PASSED_BUT_API_STILL_OPEN; requires independent check"
            conflicts += 1
        elif source_status in _OPEN:
            row["source_status_note"] = "API_REPORTED_OPEN_AT_CAPTURE; stock unverified"
        else:
            row["source_status_note"] = "SOURCE_STATUS_UNKNOWN; stock unverified"
        # An open auction API result is not proof of available inventory.
        row["stock_confidence"] = "UNVERIFIED"
        kept.append(row)

    original_batch = [id(row) for row in queue["daily_batch"]]
    queue["review_queue"] = kept
    candidates = [row for row in kept if id(row) in original_batch]
    selected = {id(row) for row in candidates}
    max_batch = len(queue["daily_batch"])
    candidates.extend(row for row in kept if id(row) not in selected)
    queue["daily_batch"] = candidates[:max_batch]
    counts["direct_waiting_for_review"] = len(kept)
    counts["daily_batch"] = len(queue["daily_batch"])
    counts["remaining"] = len(kept) - counts["daily_batch"]
    counts["auksjonen_api_matched"] = scanned
    counts["auksjonen_api_explicit_ended_held"] = ended
    counts["auksjonen_api_endtime_conflicts"] = conflicts
    counts["auksjonen_missing_from_bounded_snapshot"] = missing
    counts["auksjonen_snapshot_status"] = "DATED_SOURCE_EVIDENCE_APPLIED"
    return queue
