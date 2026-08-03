from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from alembic import command
from sqlalchemy import inspect

from opportunity_engine.persistence import (
    LifecycleEventRepository,
    UnifiedOpportunityRepository,
    build_alembic_config,
    create_database_engine,
    create_session_factory,
    persist_unified_opportunity_report,
    session_scope,
    upgrade_database,
)


ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG = ROOT / "alembic.ini"
OPPORTUNITY_ID = "lifecycle:test:1"


def _database_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'lifecycle-events.db'}"


def _record(**overrides) -> dict:
    record = {
        "opportunity_id": OPPORTUNITY_ID,
        "market_code": "NO",
        "domain": "TEXTILE_AND_SEWING",
        "category": "CLOTHING_INVENTORY",
        "title": "Parti arbeidsklær",
        "source_provider": "Auksjonen.no",
        "source_url": "https://example.test/opportunity/1",
        "listing_status": "ACTIVE",
        "evaluation_status": "REQUIRES_VERIFICATION",
        "workflow_status": "REQUIRES_VERIFICATION",
        "scenario": "AUCTION",
        "company_name": None,
        "location": None,
        "inventory_type": "workwear_inventory",
        "currency": "NOK",
        "price": None,
        "bid_price": None,
        "quantity": None,
        "published_at": None,
        "discovered_at": "2026-08-03T00:00:00Z",
        "identity_stable": True,
        "verified": False,
        "analysis_eligible": False,
        "top5_eligible": True,
        "market_signals": [],
        "evidence": [],
        "missing_information": [],
        "metadata": {"lifecycle_reason_code": "MISSING_REQUIRED_VERIFICATION"},
    }
    record.update(overrides)
    return record


def _report(record: dict, generated_at: str) -> dict:
    return {
        "schema_version": "1.1",
        "generated_at": generated_at,
        "record_count": 1,
        "records": [record],
        "conversion_error_count": 0,
        "conversion_errors": [],
    }


def test_migration_adds_and_removes_lifecycle_events_table(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path)
    upgrade_database(database_url, config_path=ALEMBIC_CONFIG)
    engine = create_database_engine(database_url)
    assert "lifecycle_events" in set(inspect(engine).get_table_names())
    engine.dispose()

    config = build_alembic_config(database_url, config_path=ALEMBIC_CONFIG)
    command.downgrade(config, "0002_unified_opportunity_v1")
    engine = create_database_engine(database_url)
    assert "lifecycle_events" not in set(inspect(engine).get_table_names())
    engine.dispose()


def test_initial_snapshot_is_recorded_once_and_replay_is_idempotent(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path)
    upgrade_database(database_url, config_path=ALEMBIC_CONFIG)
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    report = _report(_record(), "2026-08-03T00:00:00Z")

    with session_scope(factory) as session:
        repository = UnifiedOpportunityRepository(session)
        first = persist_unified_opportunity_report(report, repository)
        second = persist_unified_opportunity_report(report, repository)
        assert first["lifecycle_events_created"] == 1
        assert second["lifecycle_events_created"] == 0

    with session_scope(factory) as session:
        events = LifecycleEventRepository(session).list_for_opportunity(OPPORTUNITY_ID)
        assert len(events) == 1
        event = events[0]
        assert event.from_listing_status is None
        assert event.to_listing_status == "ACTIVE"
        assert event.from_workflow_status is None
        assert event.to_workflow_status == "REQUIRES_VERIFICATION"
        assert event.to_reason_code == "MISSING_REQUIRED_VERIFICATION"

    engine.dispose()


def test_reason_only_and_state_changes_create_append_only_events(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path)
    upgrade_database(database_url, config_path=ALEMBIC_CONFIG)
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)

    with session_scope(factory) as session:
        persist_unified_opportunity_report(
            _report(_record(), "2026-08-03T00:00:00Z"),
            UnifiedOpportunityRepository(session),
        )

    reason_changed = _record(
        metadata={"lifecycle_reason_code": "DOCUMENTED_PRICE_STILL_MISSING"}
    )
    with session_scope(factory) as session:
        summary = persist_unified_opportunity_report(
            _report(reason_changed, "2026-08-03T01:00:00Z"),
            UnifiedOpportunityRepository(session),
        )
        assert summary["lifecycle_events_created"] == 1

    qualified = deepcopy(reason_changed)
    qualified.update(
        {
            "evaluation_status": "QUALIFIED",
            "workflow_status": "QUALIFIED_OPPORTUNITY",
            "verified": True,
            "analysis_eligible": True,
            "metadata": {"lifecycle_reason_code": "QUALIFIED_CONFIRMED_SALE"},
        }
    )
    with session_scope(factory) as session:
        persist_unified_opportunity_report(
            _report(qualified, "2026-08-03T02:00:00Z"),
            UnifiedOpportunityRepository(session),
        )

    with session_scope(factory) as session:
        events = LifecycleEventRepository(session).list_for_opportunity(OPPORTUNITY_ID)
        assert len(events) == 3
        assert events[1].from_workflow_status == "REQUIRES_VERIFICATION"
        assert events[1].to_workflow_status == "REQUIRES_VERIFICATION"
        assert events[1].from_reason_code == "MISSING_REQUIRED_VERIFICATION"
        assert events[1].to_reason_code == "DOCUMENTED_PRICE_STILL_MISSING"
        assert events[2].from_evaluation_status == "REQUIRES_VERIFICATION"
        assert events[2].to_evaluation_status == "QUALIFIED"
        assert events[2].from_workflow_status == "REQUIRES_VERIFICATION"
        assert events[2].to_workflow_status == "QUALIFIED_OPPORTUNITY"
        assert events[2].to_reason_code == "QUALIFIED_CONFIRMED_SALE"

    engine.dispose()
