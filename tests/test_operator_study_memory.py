"""Contract checks for human-owned triage and durable study links."""
from datetime import datetime, timezone
import json
import sqlite3

import pytest

from opportunity_engine.operator_study_memory import export_memory, record_decision


def database(tmp_path):
    db = tmp_path / "se-exa-exact-lot" / "opportunity_engine.db"
    db.parent.mkdir()
    with sqlite3.connect(db) as connection:
        connection.execute("""CREATE TABLE unified_opportunities
            (opportunity_id TEXT PRIMARY KEY, source_url TEXT, title TEXT,
             market_code TEXT, source_provider TEXT, category TEXT, record_json TEXT)""")
        connection.execute("INSERT INTO unified_opportunities VALUES (?, ?, ?, ?, ?, ?, ?)", (
            "grossist-2359", "https://www.grossist.se/restpartier/1/20/parti/2359",
            "140 dresses", "SE", "EXA", "CLOTHING_INVENTORY",
            json.dumps({"metadata": {"page_role": "ITEM_LISTING"}}),
        ))
        connection.execute("INSERT INTO unified_opportunities VALUES (?, ?, ?, ?, ?, ?, ?)", (
            "search-page", "https://example.org/search", "Clothing search", "SE", "EXA",
            "CLOTHING_INVENTORY", json.dumps({"metadata": {"page_role": "SEARCH_RESULTS"}}),
        ))
    return db


def test_study_link_survives_without_current_search_record(tmp_path):
    db = database(tmp_path)
    first = record_decision(db, opportunity_id="grossist-2359", action="STUDY",
                            request_id="one", decided_at=datetime(2026, 9, 16, tzinfo=timezone.utc))
    replay = record_decision(db, opportunity_id="grossist-2359", action="STUDY", request_id="one")
    memory = export_memory(tmp_path)
    assert first == replay
    assert memory["audit_event_count"] == memory["explicit_decision_count"] == 1
    assert memory["study"][0]["source_url"].endswith("/parti/2359")
    assert memory["learning_review_only"][0]["status"] == "INSUFFICIENT_FEEDBACK"
    assert memory["automatic_purchase"] is False


def test_human_later_then_delete_and_learning_only_explicit(tmp_path):
    db = database(tmp_path)
    record_decision(db, opportunity_id="grossist-2359", action="STUDY", request_id="one")
    record_decision(db, opportunity_id="grossist-2359", action="LATER", request_id="two")
    memory = export_memory(tmp_path)
    assert not memory["study"] and len(memory["later"]) == 1
    assert memory["learning_review_only"] == []
    record_decision(db, opportunity_id="grossist-2359", action="DELETE", request_id="three")
    memory = export_memory(tmp_path)
    assert not memory["study"] and not memory["later"]
    assert memory["deleted_ids"] == ["grossist-2359"]
    assert memory["audit_event_count"] == 3
    assert memory["learning_review_only"][0]["delete"] == 1


def test_invalid_page_and_changed_idempotency_request_are_rejected(tmp_path):
    db = database(tmp_path)
    with pytest.raises(ValueError):
        record_decision(db, opportunity_id="search-page", action="STUDY", request_id="bad")
    record_decision(db, opportunity_id="grossist-2359", action="STUDY", request_id="same")
    with pytest.raises(ValueError):
        record_decision(db, opportunity_id="grossist-2359", action="DELETE", request_id="same")
    assert export_memory(tmp_path)["audit_event_count"] == 1
