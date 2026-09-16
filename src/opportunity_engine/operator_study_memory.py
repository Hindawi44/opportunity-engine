"""Explicit operator triage; independent of evidence verification and trading.

STUDY/DELETE/LATER are review-inbox actions, not claims about an offer's
availability or profitability. Decisions live alongside existing source SQLite
state, not in a model-generated preference or ephemeral chat selection.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any
from urllib.parse import urlsplit

ACTIONS = frozenset({"STUDY", "DELETE", "LATER"})
_SCHEMA = "operator-study-memory-1.0"


def _direct_url(value: object) -> str:
    url = str(value or "").strip()
    parsed = urlsplit(url)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("a public direct source URL is required")
    if not parsed.path.strip("/"):
        raise ValueError("homepage is not a direct source URL")
    if parsed.path.strip("/").lower() in {"search", "category", "categories", "restpartier"}:
        raise ValueError("category or search page is not a direct listing")
    return url


def _create_decision_table(connection: sqlite3.Connection) -> None:
    # Review triage has a distinct authority from fact/evidence verification.
    connection.execute("""
        CREATE TABLE IF NOT EXISTS operator_listing_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL UNIQUE,
            opportunity_id TEXT NOT NULL,
            action TEXT NOT NULL CHECK(action IN ('STUDY', 'DELETE', 'LATER')),
            source_url TEXT NOT NULL,
            title TEXT NOT NULL,
            market_code TEXT NOT NULL,
            source_provider TEXT NOT NULL,
            category TEXT NOT NULL,
            reason TEXT,
            decided_at TEXT NOT NULL
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS ix_operator_decisions_opportunity
        ON operator_listing_decisions(opportunity_id, id)
    """)


def record_decision(
    database: str | Path,
    *,
    opportunity_id: str,
    action: str,
    request_id: str,
    reason: str = "",
    decided_at: datetime | None = None,
) -> dict[str, Any]:
    """Store ONE explicit decision; replay of request_id cannot change its meaning."""
    action = action.strip().upper()
    if action not in ACTIONS:
        raise ValueError("action must be STUDY, DELETE or LATER")
    if not opportunity_id.strip() or not request_id.strip():
        raise ValueError("opportunity_id and request_id are required")
    when = decided_at or datetime.now(timezone.utc)
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError("decided_at must be timezone-aware")
    stamp = when.astimezone(timezone.utc).isoformat()
    db = Path(database)
    if not db.is_file():
        raise FileNotFoundError(f"source database missing: {db}")
    with sqlite3.connect(db) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN IMMEDIATE")
        _create_decision_table(connection)
        source = connection.execute("""
            SELECT opportunity_id, source_url, title, market_code,
                   source_provider, category, record_json
            FROM unified_opportunities WHERE opportunity_id = ?
        """, (opportunity_id.strip(),)).fetchone()
        if source is None:
            raise ValueError("opportunity identity not found in this source database")
        url = _direct_url(source["source_url"])
        raw = json.loads(source["record_json"] or "{}")
        role = str((raw.get("metadata") or {}).get("page_role") or "").upper()
        if role in {"CATEGORY", "CATEGORY_PAGE", "SEARCH", "SEARCH_RESULTS", "HOMEPAGE", "SOURCE_INDEX"}:
            raise ValueError("non-item source page cannot be reviewed as a listing")
        previous = connection.execute(
            "SELECT * FROM operator_listing_decisions WHERE request_id = ?", (request_id.strip(),)
        ).fetchone()
        if previous is not None:
            if (previous["opportunity_id"], previous["action"], previous["reason"] or "") != (
                opportunity_id.strip(), action, reason.strip()
            ):
                raise ValueError("request_id was already used for a different decision")
            return dict(previous)
        connection.execute("""
            INSERT INTO operator_listing_decisions
            (request_id, opportunity_id, action, source_url, title, market_code,
             source_provider, category, reason, decided_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (request_id.strip(), source["opportunity_id"], action, url,
              source["title"] or "Untitled source listing", source["market_code"] or "",
              source["source_provider"] or "", source["category"] or "",
              reason.strip() or None, stamp))
        row = connection.execute(
            "SELECT * FROM operator_listing_decisions WHERE request_id = ?", (request_id.strip(),)
        ).fetchone()
        return dict(row)


def export_memory(input_root: str | Path) -> dict[str, Any]:
    """Rehydrate bookmarked URLs even when absent from today's search results."""
    latest: dict[str, dict[str, Any]] = {}
    history_count = 0
    for database in sorted(Path(input_root).glob("*/opportunity_engine.db")):
        with sqlite3.connect(database) as connection:
            connection.row_factory = sqlite3.Row
            table = connection.execute("""
                SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = 'operator_listing_decisions'
            """).fetchone()
            if table is None:
                continue
            for row in connection.execute("SELECT * FROM operator_listing_decisions ORDER BY id"):
                item = dict(row)
                history_count += 1
                key = item["opportunity_id"]
                prior = latest.get(key)
                if prior is None or (item["decided_at"], item["id"], str(database)) > (
                    prior["decided_at"], prior["id"], prior["database"]
                ):
                    item["database"] = str(database)
                    latest[key] = item
    decisions = sorted(latest.values(), key=lambda x: (x["decided_at"], x["opportunity_id"]))
    studies = [row for row in decisions if row["action"] == "STUDY"]
    later = [row for row in decisions if row["action"] == "LATER"]
    deleted = [row for row in decisions if row["action"] == "DELETE"]
    # Never treat LATER or a missing decision as negative feedback.
    groups: dict[str, Counter[str]] = {}
    for item in studies + deleted:
        for dimension in ("market_code", "source_provider", "category"):
            value = item.get(dimension) or "UNKNOWN"
            key = f"{dimension}:{value}"
            groups.setdefault(key, Counter())[item["action"]] += 1
    learning = [
        {"segment": segment, "study": counts["STUDY"], "delete": counts["DELETE"],
         "evidence_count": sum(counts.values()),
         "status": "INSUFFICIENT_FEEDBACK" if sum(counts.values()) < 5 else "REVIEW_ONLY_PATTERN"}
        for segment, counts in sorted(groups.items())
    ]
    return {
        "schema_version": _SCHEMA,
        "study": studies, "later": later, "deleted_ids": sorted(x["opportunity_id"] for x in deleted),
        "explicit_decision_count": len(decisions), "audit_event_count": history_count,
        "learning_review_only": learning,
        "automatic_contact": False, "automatic_bid": False,
        "automatic_purchase": False, "automatic_payment": False,
        "automatic_source_exclusion": False, "automatic_query_activation": False,
    }
