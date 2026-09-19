"""The explicit listing-5 DELETE must never exclude Salzmann as a domain."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from opportunity_engine.operator_decision_ingest import ingest_explicit_events
from opportunity_engine.operator_study_memory import export_memory

EVENTS = Path("config/operator-review-events-v1.json")
LISTING5 = (
    "https://salzmann-restwaren.de/product/"
    "bekleidung-versch-marken-groessen-blazer-t-shirts-longsleeves-oberteile-mix/"
)
LISTING4 = (
    "https://salzmann-restwaren.de/product/"
    "bekleidung-fuer-herren-pullover-cardigans-blusen-shirts-jacken-strickwaren/"
)
REQUEST = "explicit-chat-2026-09-19-salzmann-gh_sal32205-1-delete"


def test_listing5_explicit_event_is_listing_scoped_and_not_stock_or_domain_claim():
    events = json.loads(EVENTS.read_text(encoding="utf-8"))["events"]
    matching = [event for event in events if event["request_id"] == REQUEST]
    assert len(matching) == 1
    event = matching[0]
    assert (event["authority"], event["review_run"], event["review_position"]) == ("EXPLICIT_USER", 503, 5)
    assert event["action"] == "DELETE"
    assert event["source_url"] == event["opportunity_id"] == LISTING5
    assert event["database_relative_path"] == "de-exa-exact-lot/opportunity_engine.db"
    assert event["preserve_historical_discovery"] is True
    assert event["stock_confirmed"] is False and event["purchase_approved"] is False
    assert "NOT_DOMAIN_EXCLUSION_OR_STOCK_CLAIM" in event["scope"]
    assert "GH_SAL32205-1" in event["reason"]
    assert "Do not block salzmann-restwaren.de" in event["reason"]
    assert LISTING4 != LISTING5
    assert len([e for e in events if e["opportunity_id"] == LISTING5]) == 1


def test_listing5_sqlite_replay_preserves_listing4_and_original_rows(tmp_path):
    events = json.loads(EVENTS.read_text(encoding="utf-8"))["events"]
    assert len(events) >= 3
    selected = [e for e in events if e["request_id"] in {
        REQUEST, "explicit-chat-2026-09-19-salzmann-gh_han03112-20-study",
        "explicit-chat-2026-09-18-bijuymoda-3445-delete",
    }]
    assert len(selected) == 3
    path = tmp_path / "events.json"
    path.write_text(json.dumps({"schema_version": "operator-review-events-v1", "events": selected}), encoding="utf-8")
    root = tmp_path / "sources"
    for event in selected:
        db = root / event["database_relative_path"]
        db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS unified_opportunities (
                opportunity_id TEXT PRIMARY KEY, source_url TEXT, title TEXT,
                market_code TEXT, source_provider TEXT, category TEXT, record_json TEXT
            )""")
            conn.execute("INSERT INTO unified_opportunities VALUES (?,?,?,?,?,?,?)", (
                event["opportunity_id"], event["source_url"], "Historical listing",
                "DE" if event["database_relative_path"].startswith("de-") else "IT",
                "EXA", "CLOTHING_INVENTORY", json.dumps({"metadata": {"page_role": "ITEM_LISTING"}}),
            ))
    first = ingest_explicit_events(root, events_path=path)
    second = ingest_explicit_events(root, events_path=path)
    assert first["status"] == second["status"] == "VERIFIED_SQLITE_COMMITTED"
    assert first["events_committed_or_replayed"] == second["events_committed_or_replayed"] == 3
    db = root / "de-exa-exact-lot/opportunity_engine.db"
    with sqlite3.connect(db) as conn:
        committed = conn.execute(
            "SELECT opportunity_id, action, source_url, reason FROM operator_listing_decisions WHERE request_id=?", (REQUEST,)
        ).fetchone()
        assert committed is not None and committed[:3] == (LISTING5, "DELETE", LISTING5)
        assert "not infer sold-out" in committed[3]
        assert conn.execute("SELECT COUNT(*) FROM unified_opportunities").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM operator_listing_decisions").fetchone()[0] == 2
        assert conn.execute("SELECT action FROM operator_listing_decisions WHERE opportunity_id=?", (LISTING4,)).fetchone()[0] == "STUDY"
    memory = export_memory(root)
    assert LISTING5 in memory["deleted_ids"] and LISTING4 not in memory["deleted_ids"]
    assert any(study["opportunity_id"] == LISTING4 for study in memory["study"])
    assert memory["audit_event_count"] == 3
    assert memory["automatic_source_exclusion"] is False
    assert memory["automatic_purchase"] is False and memory["automatic_contact"] is False
