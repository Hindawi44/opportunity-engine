"""The operator's listing-4 study must persist without claiming inventory or a purchase."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from opportunity_engine.operator_decision_ingest import ingest_explicit_events
from opportunity_engine.operator_study_memory import export_memory

EVENTS = Path("config/operator-review-events-v1.json")
STUDY = Path("config/operator-studies-v1/de-salzmann-gh_han03112-20.json")
SALZMANN_URL = (
    "https://salzmann-restwaren.de/product/"
    "bekleidung-fuer-herren-pullover-cardigans-blusen-shirts-jacken-strickwaren/"
)


def test_study_evidence_source_attribution_and_review_only_authority():
    study = json.loads(STUDY.read_text(encoding="utf-8"))
    payload = json.loads(EVENTS.read_text(encoding="utf-8"))
    matching = [event for event in payload["events"] if event["source_url"] == SALZMANN_URL]
    assert len(matching) == 1
    event = matching[0]
    assert event["authority"] == "EXPLICIT_USER"
    assert event["action"] == "STUDY"
    assert event["opportunity_id"] == SALZMANN_URL
    assert event["database_relative_path"] == "de-exa-exact-lot/opportunity_engine.db"
    assert event["study_evidence_path"] == str(STUDY)
    assert event["stock_confirmed"] is False and event["purchase_approved"] is False
    assert study["study_id"] == event["request_id"]
    assert study["source_url"] == event["source_url"]
    assert study["source_evidence"]["article_number"] == "GH_HAN03112-20"
    assert study["source_evidence"]["advertised_quantity_pieces"] == 44
    assert study["source_evidence"]["advertised_price_from_eur_net"] == 2.88
    assert study["source_evidence"]["evidence_level"].endswith("NOT_STOCK_VERIFIED")
    assert "independently" in study["unverified_or_missing"][0]
    assert study["stock_confirmed"] is False
    assert study["purchase_approved"] is False
    assert study["automatic_purchase"] is False
    assert study["automatic_contact"] is False
    assert study["historical_source_record_preserved"] is True
    assert len(payload["events"]) == 2  # Existing Bijuymoda exclusion is preserved.


def test_study_ingests_idempotently_into_existing_sqlite_memory(tmp_path):
    events = json.loads(EVENTS.read_text(encoding="utf-8"))["events"]
    root = tmp_path / "multi-market-inputs"
    for event in events:
        db = root / event["database_relative_path"]
        db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db) as connection:
            connection.execute("""CREATE TABLE unified_opportunities (
                opportunity_id TEXT PRIMARY KEY, source_url TEXT, title TEXT,
                market_code TEXT, source_provider TEXT, category TEXT, record_json TEXT
            )""")
            connection.execute("INSERT INTO unified_opportunities VALUES (?, ?, ?, ?, ?, ?, ?)", (
                event["opportunity_id"], event["source_url"],
                "Archived source listing", "DE" if event["action"] == "STUDY" else "IT",
                "EXA", "CLOTHING_INVENTORY",
                json.dumps({"metadata": {"page_role": "ITEM_LISTING"}}),
            ))
    first = ingest_explicit_events(root, events_path=EVENTS)
    replay = ingest_explicit_events(root, events_path=EVENTS)
    assert first["status"] == replay["status"] == "VERIFIED_SQLITE_COMMITTED"
    assert first["events_committed_or_replayed"] == 2
    assert first["automatic_purchase"] is False
    assert first["automatic_contact"] is False

    db = root / "de-exa-exact-lot" / "opportunity_engine.db"
    with sqlite3.connect(db) as connection:
        row = connection.execute("""SELECT action, source_url, reason
            FROM operator_listing_decisions WHERE opportunity_id = ?""", (SALZMANN_URL,)).fetchone()
        assert row is not None and row[0] == "STUDY" and row[1] == SALZMANN_URL
        assert str(STUDY) in row[2] and "44 pieces" in row[2]
        assert connection.execute("SELECT COUNT(*) FROM operator_listing_decisions").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM unified_opportunities").fetchone()[0] == 1
    memory = export_memory(root)
    assert memory["audit_event_count"] == 2
    assert len(memory["study"]) == 1
    assert memory["study"][0]["source_url"] == SALZMANN_URL
    assert len(memory["deleted_ids"]) == 1
    assert memory["automatic_purchase"] is False
    assert memory["automatic_source_exclusion"] is False
