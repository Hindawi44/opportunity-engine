"""Commit human-authored review events into the EXISTING SQLite decision history.

The repository event file is a replayable input, never a parallel source of
review state. Each event is checked against an actual persisted source record;
missing, changed, or non-item URLs fail closed. No commercial state changes.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from opportunity_engine.operator_study_memory import record_decision

DEFAULT_EVENTS = Path("config/operator-review-events-v1.json")
_DATABASE_PATH = re.compile(r"^[a-z]{2}(?:-[a-z0-9]+)+/opportunity_engine\.db$")


def ingest_explicit_events(input_root: str | Path, *,
                           events_path: str | Path = DEFAULT_EVENTS) -> dict[str, Any]:
    """Replay explicitly recorded operator actions, verifying committed rows."""
    path = Path(events_path)
    result: dict[str, Any] = {
        "schema_version": "operator-review-event-ingest-v1",
        "status": "NO_EVENT_FILE", "events_seen": 0,
        "events_committed_or_replayed": 0, "automatic_review_decisions": False,
        "automatic_purchase": False, "automatic_contact": False,
    }
    if not path.is_file():
        return result
    if path.stat().st_size > 128_000:
        raise ValueError("review event file exceeds the bounded limit")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != "operator-review-events-v1":
        raise ValueError("invalid operator review event schema")
    events = payload.get("events")
    if not isinstance(events, list) or len(events) > 100:
        raise ValueError("invalid or excessive operator review events")
    result["events_seen"] = len(events)
    root = Path(input_root)
    for event in events:
        if not isinstance(event, dict) or event.get("authority") != "EXPLICIT_USER":
            raise ValueError("operator event requires explicit user authority")
        relative = event.get("database_relative_path")
        if not isinstance(relative, str) or not _DATABASE_PATH.fullmatch(relative):
            raise ValueError("unsupported source database path")
        db = root / relative
        if not db.is_file():
            raise FileNotFoundError(f"review source database missing: {db}")
        opportunity_id = event.get("opportunity_id")
        source_url = event.get("source_url")
        request_id = event.get("request_id")
        if not all(isinstance(value, str) and value.strip() for value in
                   (opportunity_id, source_url, request_id)):
            raise ValueError("review event identity, URL and request ID are required")
        with sqlite3.connect(db) as connection:
            source = connection.execute(
                "SELECT source_url FROM unified_opportunities WHERE opportunity_id = ?",
                (opportunity_id,),
            ).fetchone()
        if source is None or source[0] != source_url:
            raise ValueError("review event URL is not backed by its exact persisted listing")
        when = event.get("decided_at")
        if not isinstance(when, str):
            raise ValueError("review event requires a human-decision timestamp")
        decided_at = datetime.fromisoformat(when)
        if decided_at.tzinfo is None or decided_at.utcoffset() is None:
            raise ValueError("review decision timestamp must have a timezone")
        action = event.get("action")
        if not isinstance(action, str):
            raise ValueError("invalid review action")
        decision = record_decision(
            db, opportunity_id=opportunity_id, action=action,
            request_id=request_id, reason=str(event.get("reason") or ""),
            decided_at=decided_at,
        )
        # Reopen the database: success is acknowledged only after a durable commit.
        with sqlite3.connect(db) as connection:
            persisted = connection.execute(
                "SELECT opportunity_id, action, source_url FROM operator_listing_decisions WHERE request_id = ?",
                (request_id,),
            ).fetchone()
        if persisted != (opportunity_id, action.strip().upper(), source_url):
            raise RuntimeError("operator decision was not committed to SQLite")
        result["events_committed_or_replayed"] += 1
        result["last_event_request_id"] = decision["request_id"]
    result["status"] = "VERIFIED_SQLITE_COMMITTED" if events else "NO_EVENTS"
    return result
