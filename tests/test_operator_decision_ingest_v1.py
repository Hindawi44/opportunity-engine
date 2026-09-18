"""Explicit review decision bridging must be durable, idempotent, and non-commercial."""
import json
import sqlite3

import pytest

from opportunity_engine.operator_decision_ingest import ingest_explicit_events
from opportunity_engine.operator_study_memory import export_memory
from opportunity_engine.human_listing_review_queue import build_queue

URL = "https://bijuymoda.com/it/lotti-in-offerta-all-ingrosso/3445-stock-all-ingrosso-di-abbigliamento-e-scarpe-ampia-varieta-di-marche-e-modelli.html"


def setup(tmp_path):
    root = tmp_path / "inputs"
    db = root / "it-exa-exact-lot" / "opportunity_engine.db"
    db.parent.mkdir(parents=True)
    with sqlite3.connect(db) as connection:
        connection.execute("""CREATE TABLE unified_opportunities
            (opportunity_id TEXT PRIMARY KEY, source_url TEXT, title TEXT,
             market_code TEXT, source_provider TEXT, category TEXT, record_json TEXT)""")
        connection.execute("INSERT INTO unified_opportunities VALUES (?, ?, ?, ?, ?, ?, ?)", (
            URL, URL, "Bijuymoda 3445", "IT", "EXA", "CLOTHING_INVENTORY",
            json.dumps({"metadata": {"page_role": "ITEM_LISTING"}}),
        ))
    events = tmp_path / "events.json"
    payload = {"schema_version": "operator-review-events-v1", "events": [
        {"request_id": "user-message-1", "authority": "EXPLICIT_USER",
         "database_relative_path": "it-exa-exact-lot/opportunity_engine.db",
         "opportunity_id": URL, "source_url": URL, "action": "DELETE", "reason": "",
         "decided_at": "2026-09-18T10:21:00+02:00"}
    ]}
    events.write_text(json.dumps(payload), encoding="utf-8")
    return root, db, events, payload


def test_explicit_delete_commits_once_preserves_source_and_disappears_from_review(tmp_path):
    root, db, events, _ = setup(tmp_path)
    first = ingest_explicit_events(root, events_path=events)
    second = ingest_explicit_events(root, events_path=events)
    assert first["status"] == second["status"] == "VERIFIED_SQLITE_COMMITTED"
    assert first["events_committed_or_replayed"] == 1
    assert first["automatic_review_decisions"] is False
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM operator_listing_decisions").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM unified_opportunities WHERE source_url=?", (URL,)).fetchone()[0] == 1
        action, stamp = connection.execute("SELECT action, decided_at FROM operator_listing_decisions").fetchone()
        assert action == "DELETE" and stamp == "2026-09-18T08:21:00+00:00"
    memory = export_memory(root)
    assert memory["deleted_ids"] == [URL]
    assert memory["audit_event_count"] == 1
    report = {"deduplicated_opportunities": [{"opportunity_identity": URL, "canonical_url": URL,
              "market_code": "IT", "listing_status": "ACTIVE", "source_names": ["Exa Exact-Lot IT"]}]}
    queue = build_queue(report, memory)
    assert not queue["review_queue"] and queue["counts"]["operator_deleted"] == 1
    assert len(report["deduplicated_opportunities"]) == 1


def test_unmatched_or_forged_url_is_not_saved(tmp_path):
    root, db, events, payload = setup(tmp_path)
    payload["events"][0]["source_url"] = "https://different.invalid/product/1"
    events.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="exact persisted listing"):
        ingest_explicit_events(root, events_path=events)
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='operator_listing_decisions'").fetchone() is None


def test_no_inferred_decisions_and_no_path_traversal(tmp_path):
    root, _, events, payload = setup(tmp_path)
    assert ingest_explicit_events(root, events_path=tmp_path / "absent.json")["status"] == "NO_EVENT_FILE"
    payload["events"][0]["authority"] = "MODEL_INFERRED"
    events.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="explicit user"):
        ingest_explicit_events(root, events_path=events)
    payload["events"][0]["authority"] = "EXPLICIT_USER"
    payload["events"][0]["database_relative_path"] = "../elsewhere/opportunity_engine.db"
    events.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported source"):
        ingest_explicit_events(root, events_path=events)


def test_direct_source_role_gate_is_preserved(tmp_path):
    root, db, events, _ = setup(tmp_path)
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE unified_opportunities SET record_json=? WHERE opportunity_id=?",
                           (json.dumps({"metadata":{"page_role":"CATEGORY_PAGE"}}), URL))
    with pytest.raises(ValueError, match="non-item"):
        ingest_explicit_events(root, events_path=events)
