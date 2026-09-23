from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from scripts.restore_norway_review_state import configure_norway_only_restore
from scripts.run_norway_review_cycle import run_review_cycle
from opportunity_engine.discovery import checkpoint_state_restore


ROOT = Path(__file__).resolve().parents[1]
URL = "https://www.auksjonen.no/auksjon/torget/Parti_kontormobler/700001"


def _direct_report(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "scope": "NO_ONLY_ALL_ASSETS",
                "captured_at": "2026-09-23T08:00:00+00:00",
                "requested_cards": 1,
                "verified_count": 1,
                "pages_read": 1,
                "distinct_active_api_candidates": 1,
                "cards": [
                    {
                        "object_id": 700001,
                        "title": "Parti kontormøbler",
                        "url": URL,
                        "asset_type": "Parti kontormøbler",
                        "location": "Namsos",
                        "current_bid_nok": 500.0,
                        "buy_now_nok": None,
                        "start_price_nok": 0.0,
                        "ends_at": "2026-09-25T12:00:00+00:00",
                        "status": "ACTIVE_VERIFIED_AT_CHECK",
                        "verified_at": "2026-09-23T08:00:00+00:00",
                    }
                ],
                "failures": [],
                "missing_count": 0,
                "paid_api_requests": 0,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _events(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "operator-review-events-v1",
                "events": [
                    {
                        "request_id": "no-study-1",
                        "authority": "EXPLICIT_USER",
                        "database_relative_path": "no-auksjonen/opportunity_engine.db",
                        "opportunity_id": URL,
                        "source_url": URL,
                        "action": "STUDY",
                        "reason": "operator asked to study this exact Norwegian lot",
                        "decided_at": "2026-09-23T10:05:00+02:00",
                    },
                    {
                        "request_id": "de-delete-history",
                        "authority": "EXPLICIT_USER",
                        "database_relative_path": "de-exa-exact-lot/opportunity_engine.db",
                        "opportunity_id": "https://example.de/product/1",
                        "source_url": "https://example.de/product/1",
                        "action": "DELETE",
                        "reason": "",
                        "decided_at": "2026-09-23T10:06:00+02:00",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_review_cycle_persists_norway_listing_and_explicit_study_only(tmp_path: Path) -> None:
    direct = tmp_path / "direct-sales.json"
    events = tmp_path / "events.json"
    input_root = tmp_path / "inputs"
    output = tmp_path / "review"
    _direct_report(direct)
    _events(events)

    first = run_review_cycle(
        direct_sales_path=direct,
        input_root=input_root,
        output_dir=output,
        events_path=events,
        config_path=ROOT / "alembic.ini",
    )
    second = run_review_cycle(
        direct_sales_path=direct,
        input_root=input_root,
        output_dir=output,
        events_path=events,
        config_path=ROOT / "alembic.ini",
    )

    assert first["direct_cards_persisted"] == second["direct_cards_persisted"] == 1
    assert first["operator_event_scope"] == {
        "events_total": 2,
        "events_norway": 1,
        "events_out_of_scope_preserved_not_ingested": 1,
    }
    assert first["operator_ingestion"]["status"] == "VERIFIED_SQLITE_COMMITTED"
    assert first["memory"]["study"] == 1
    assert first["memory"]["explicit_decision_count"] == 1
    assert first["review_queue_counts"]["in_study_memory"] == 1
    assert first["review_queue_counts"]["daily_batch"] == 0
    assert first["automatic_query_activation"] is False
    assert first["automatic_purchase"] is False

    database = input_root / "no-auksjonen" / "opportunity_engine.db"
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM unified_opportunities WHERE opportunity_id = ?", (URL,)
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM operator_listing_decisions"
        ).fetchone()[0] == 1
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"


def test_review_cycle_preserves_legacy_human_review_history(tmp_path: Path) -> None:
    direct = tmp_path / "direct-sales.json"
    input_root = tmp_path / "inputs"
    output = tmp_path / "review"
    _direct_report(direct)

    # First create/migrate the canonical Norwegian database.
    run_review_cycle(
        direct_sales_path=direct,
        input_root=input_root,
        output_dir=output,
        events_path=tmp_path / "absent-events.json",
        config_path=ROOT / "alembic.ini",
    )
    database = input_root / "no-auksjonen" / "opportunity_engine.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO human_review_outcomes
            (review_key, opportunity_id, outcome, reviewer, note, source_ref, reviewed_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-review-key",
                URL,
                "VERIFIED",
                "Hindawi44",
                "historical manual review",
                "historical-artifact",
                "2026-08-03 10:00:00",
                "2026-08-03 10:00:00",
            ),
        )

    status = run_review_cycle(
        direct_sales_path=direct,
        input_root=input_root,
        output_dir=output,
        events_path=tmp_path / "absent-events.json",
        config_path=ROOT / "alembic.ini",
    )
    assert status["legacy_review_history"]["legacy_human_review_outcomes"] == 1
    assert status["memory"]["explicit_decision_count"] == 0


def test_restore_configuration_is_norway_only_and_keeps_main_push_continuity() -> None:
    original_paths = checkpoint_state_restore.DATABASE_RELATIVE_PATHS
    original_learning = checkpoint_state_restore.LEARNING_STATE_FILENAMES
    original_follow_up = checkpoint_state_restore.FOLLOW_UP_SEED_MEMBERS
    original_events = checkpoint_state_restore.RESTORABLE_EVENTS
    try:
        configure_norway_only_restore()
        assert checkpoint_state_restore.DATABASE_RELATIVE_PATHS
        assert all(
            path.startswith("no-")
            for path in checkpoint_state_restore.DATABASE_RELATIVE_PATHS
        )
        assert checkpoint_state_restore.LEARNING_STATE_FILENAMES == ()
        assert checkpoint_state_restore.FOLLOW_UP_SEED_MEMBERS == ()
        assert checkpoint_state_restore.RESTORABLE_EVENTS == {
            "workflow_dispatch",
            "schedule",
            "push",
        }
    finally:
        checkpoint_state_restore.DATABASE_RELATIVE_PATHS = original_paths
        checkpoint_state_restore.LEARNING_STATE_FILENAMES = original_learning
        checkpoint_state_restore.FOLLOW_UP_SEED_MEMBERS = original_follow_up
        checkpoint_state_restore.RESTORABLE_EVENTS = original_events
