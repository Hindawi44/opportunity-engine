"""Nipa Stock lot 120: explicit review DELETE, preserving source history and seller scope."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from opportunity_engine.human_listing_review_queue import build_queue, classify_url
from opportunity_engine.operator_decision_ingest import ingest_explicit_events
from opportunity_engine.operator_study_memory import export_memory

EVENTS = Path("config/operator-review-events-v1.json")
NIPA = "https://nipa-stock.com/it/product/assortiment-brendovoj-stokovoj-odezhdy-iz-germanii-kategoriya-avs"
# Clearly synthetic second source fixture: never treated as a real listing.
OTHER_NIPA = "https://nipa-stock.com/it/product/other-test-record"
REQUEST = "explicit-chat-2026-09-19-nipa-stock-lot120-delete"
PRIOR_REQUESTS = {
    "explicit-chat-2026-09-18-bijuymoda-3445-delete",
    "explicit-chat-2026-09-19-salzmann-gh_han03112-20-study",
    "explicit-chat-2026-09-19-salzmann-gh_sal32205-1-delete",
    "explicit-chat-2026-09-19-cube-company-listing6-delete",
}


def selected_events():
    payload = json.loads(EVENTS.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "operator-review-events-v1"
    selected = [e for e in payload["events"] if e["request_id"] in PRIOR_REQUESTS | {REQUEST}]
    assert len(selected) == 5
    assert {e["request_id"] for e in selected} == PRIOR_REQUESTS | {REQUEST}
    return selected


def test_nipa_delete_is_exact_and_preserves_prior_decision_events():
    events = selected_events()
    target, = [e for e in events if e["request_id"] == REQUEST]
    assert (target["authority"], target["review_run"], target["review_position"]) == (
        "EXPLICIT_USER", 503, 7,
    )
    assert target["action"] == "DELETE"
    assert target["opportunity_id"] == target["source_url"] == NIPA
    assert target["database_relative_path"] == "it-exa-exact-lot/opportunity_engine.db"
    assert target["preserve_historical_discovery"] is True
    assert target["stock_confirmed"] is False and target["purchase_approved"] is False
    assert "NOT_DOMAIN_EXCLUSION_OR_STOCK_CLAIM" in target["scope"]
    assert "Do not exclude nipa-stock.com" in target["reason"]
    assert OTHER_NIPA != NIPA


def test_nipa_exact_sqlite_commit_replay_preserves_sources_and_other_decisions(tmp_path):
    selected = selected_events()
    event_file = tmp_path / "events.json"
    event_file.write_text(json.dumps({"schema_version": "operator-review-events-v1", "events": selected}), encoding="utf-8")
    root = tmp_path / "multi-market-inputs"
    for event in selected:
        database = root / event["database_relative_path"]
        database.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS unified_opportunities (
                opportunity_id TEXT PRIMARY KEY, source_url TEXT, title TEXT,
                market_code TEXT, source_provider TEXT, category TEXT, record_json TEXT
            )""")
            conn.execute("INSERT INTO unified_opportunities VALUES (?,?,?,?,?,?,?)", (
                event["opportunity_id"], event["source_url"], "Historical listing",
                event["database_relative_path"][:2].upper(), "EXA", "CLOTHING_INVENTORY",
                json.dumps({"metadata": {"page_role": "ITEM_LISTING"}}),
            ))
    italy = root / "it-exa-exact-lot/opportunity_engine.db"
    with sqlite3.connect(italy) as conn:
        conn.execute("INSERT INTO unified_opportunities VALUES (?,?,?,?,?,?,?)", (
            OTHER_NIPA, OTHER_NIPA, "Synthetic second Nipa listing", "IT", "EXA",
            "CLOTHING_INVENTORY", json.dumps({"metadata": {"page_role": "ITEM_LISTING"}}),
        ))
    first = ingest_explicit_events(root, events_path=event_file)
    second = ingest_explicit_events(root, events_path=event_file)
    assert first["status"] == second["status"] == "VERIFIED_SQLITE_COMMITTED"
    assert first["events_seen"] == second["events_seen"] == 5
    assert first["events_committed_or_replayed"] == second["events_committed_or_replayed"] == 5
    assert first["last_event_request_id"] == REQUEST
    assert first["automatic_review_decisions"] is False
    assert first["automatic_contact"] is False and first["automatic_purchase"] is False
    with sqlite3.connect(italy) as conn:
        saved = conn.execute("""SELECT opportunity_id, action, source_url, reason
            FROM operator_listing_decisions WHERE request_id=?""", (REQUEST,)).fetchone()
        assert saved is not None and saved[:3] == (NIPA, "DELETE", NIPA)
        assert "Do not exclude nipa-stock.com" in saved[3]
        assert conn.execute("SELECT COUNT(*) FROM operator_listing_decisions").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM unified_opportunities").fetchone()[0] == 3
        assert conn.execute("SELECT COUNT(*) FROM unified_opportunities WHERE opportunity_id=?", (NIPA,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM unified_opportunities WHERE opportunity_id=?", (OTHER_NIPA,)).fetchone()[0] == 1
        assert conn.execute("SELECT action FROM operator_listing_decisions WHERE request_id=?", (
            "explicit-chat-2026-09-18-bijuymoda-3445-delete",)).fetchone()[0] == "DELETE"
    memory = export_memory(root)
    assert memory["audit_event_count"] == memory["explicit_decision_count"] == 5
    assert NIPA in memory["deleted_ids"] and OTHER_NIPA not in memory["deleted_ids"]
    assert len(memory["study"]) == 1 and "salzmann-restwaren.de" in memory["study"][0]["source_url"]
    assert memory["automatic_source_exclusion"] is False
    assert memory["automatic_contact"] is False and memory["automatic_purchase"] is False


def test_nipa_delete_suppresses_held_and_direct_queue_without_blacklisting_seller():
    def row(url):
        return {"opportunity_identity": url, "title": "Test listing",
                "canonical_url": None, "source_urls": [url], "market_code": "IT",
                "listing_status": "ACTIVE", "source_names": ["Exa Exact-Lot IT"]}
    report = {"deduplicated_opportunities": [row(NIPA), row(OTHER_NIPA)]}
    before = build_queue(report)
    assert any(r["identity"] == NIPA for r in before["held_separately"])
    after = build_queue(report, {"deleted_ids": [NIPA], "study": [], "later": []})
    assert len(report["deduplicated_opportunities"]) == 2
    assert after["counts"]["discovered_records"] == 2
    assert after["counts"]["operator_deleted"] == 1
    assert all(r.get("identity") != NIPA for section in (
        "daily_batch", "review_queue", "held_separately") for r in after[section])
    assert any(r["identity"] == OTHER_NIPA for r in after["held_separately"])
    assert classify_url(OTHER_NIPA) != "EXCLUDED"
