"""Explicit listing-6 DELETE must suppress one review identity, never a site or source history."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from opportunity_engine.human_listing_review_queue import build_queue, classify_url
from opportunity_engine.operator_decision_ingest import ingest_explicit_events
from opportunity_engine.operator_study_memory import export_memory

EVENTS = Path("config/operator-review-events-v1.json")
CUBE = (
    "https://cubecompany.nl/product/"
    "partij-herenkleding-jack-jones-only-sons-petrol-industries-1050-stuks/"
)
OTHER_CUBE = (
    "https://cubecompany.nl/product/"
    "kledingpartij-dameskleding-alix-the-label-drykorn-kocca-etc-600-stuks/"
)
REQUEST = "explicit-chat-2026-09-19-cube-company-listing6-delete"
OLDER_REQUESTS = {
    "explicit-chat-2026-09-18-bijuymoda-3445-delete",
    "explicit-chat-2026-09-19-salzmann-gh_han03112-20-study",
    "explicit-chat-2026-09-19-salzmann-gh_sal32205-1-delete",
}


def events():
    payload = json.loads(EVENTS.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "operator-review-events-v1"
    return payload["events"]


def test_cube_event_has_exact_review_scope_and_preserves_prior_human_actions():
    recorded = events()
    assert len(recorded) == 4
    assert {event["request_id"] for event in recorded} == OLDER_REQUESTS | {REQUEST}
    cube, = [event for event in recorded if event["request_id"] == REQUEST]
    assert (cube["authority"], cube["review_run"], cube["review_position"]) == (
        "EXPLICIT_USER", 503, 6,
    )
    assert cube["database_relative_path"] == "nl-exa-exact-lot/opportunity_engine.db"
    assert cube["opportunity_id"] == cube["source_url"] == CUBE
    assert cube["action"] == "DELETE"
    assert cube["preserve_historical_discovery"] is True
    assert cube["stock_confirmed"] is False and cube["purchase_approved"] is False
    assert "NOT_DOMAIN_EXCLUSION_OR_STOCK_CLAIM" in cube["scope"]
    assert "Do not exclude cubecompany.nl" in cube["reason"]
    assert CUBE != OTHER_CUBE


def test_cube_sqlite_replay_preserves_historical_sources_and_older_decisions(tmp_path):
    recorded = events()
    root = tmp_path / "multi-market-inputs"
    for event in recorded:
        db = root / event["database_relative_path"]
        db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS unified_opportunities (
                opportunity_id TEXT PRIMARY KEY, source_url TEXT, title TEXT,
                market_code TEXT, source_provider TEXT, category TEXT, record_json TEXT
            )""")
            conn.execute("INSERT INTO unified_opportunities VALUES (?,?,?,?,?,?,?)", (
                event["opportunity_id"], event["source_url"], "Historical source listing",
                event["database_relative_path"][:2].upper(), "EXA", "CLOTHING_INVENTORY",
                json.dumps({"metadata": {"page_role": "ITEM_LISTING"}}),
            ))
    # A second product from Cube must not be affected by the exact listing decision.
    nl_db = root / "nl-exa-exact-lot/opportunity_engine.db"
    with sqlite3.connect(nl_db) as conn:
        conn.execute("INSERT INTO unified_opportunities VALUES (?,?,?,?,?,?,?)", (
            OTHER_CUBE, OTHER_CUBE, "Another Cube product", "NL", "EXA",
            "CLOTHING_INVENTORY", json.dumps({"metadata": {"page_role": "ITEM_LISTING"}}),
        ))
    first = ingest_explicit_events(root, events_path=EVENTS)
    second = ingest_explicit_events(root, events_path=EVENTS)
    assert first["status"] == second["status"] == "VERIFIED_SQLITE_COMMITTED"
    assert first["events_committed_or_replayed"] == second["events_committed_or_replayed"] == 4
    assert first["automatic_purchase"] is False and first["automatic_contact"] is False
    with sqlite3.connect(nl_db) as conn:
        saved = conn.execute(
            "SELECT opportunity_id, action, source_url, reason FROM operator_listing_decisions "
            "WHERE request_id=?", (REQUEST,),
        ).fetchone()
        assert saved is not None and saved[:3] == (CUBE, "DELETE", CUBE)
        assert "Do not exclude cubecompany.nl" in saved[3]
        assert conn.execute("SELECT COUNT(*) FROM unified_opportunities").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM operator_listing_decisions").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM unified_opportunities WHERE opportunity_id=?", (CUBE,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM unified_opportunities WHERE opportunity_id=?", (OTHER_CUBE,)).fetchone()[0] == 1
    memory = export_memory(root)
    assert memory["audit_event_count"] == 4
    assert memory["explicit_decision_count"] == 4
    assert CUBE in memory["deleted_ids"] and OTHER_CUBE not in memory["deleted_ids"]
    assert len(memory["study"]) == 1 and "salzmann-restwaren.de" in memory["study"][0]["source_url"]
    assert memory["automatic_source_exclusion"] is False
    assert memory["automatic_contact"] is False and memory["automatic_purchase"] is False


def test_delete_applies_before_held_classification_without_domain_blacklist():
    def row(url):
        return {"opportunity_identity": url, "title": "Historical source listing",
                "canonical_url": None, "source_urls": [url],
                "market_code": "NL", "listing_status": "ACTIVE",
                "source_names": ["Exa Exact-Lot NL"]}

    report = {"deduplicated_opportunities": [row(CUBE), row(OTHER_CUBE)]}
    before = build_queue(report)
    assert any(r["identity"] == CUBE for r in before["held_separately"])
    after = build_queue(report, {"deleted_ids": [CUBE], "study": [], "later": []})
    assert len(report["deduplicated_opportunities"]) == 2  # Historical input unchanged.
    assert after["counts"]["discovered_records"] == 2
    assert after["counts"]["operator_deleted"] == 1
    assert all(r.get("identity") != CUBE for section in (
        "daily_batch", "review_queue", "held_separately") for r in after[section])
    assert any(r["identity"] == OTHER_CUBE for r in after["held_separately"])
    assert classify_url(OTHER_CUBE) != "EXCLUDED"
