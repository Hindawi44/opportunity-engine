from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from alembic import command
import pytest
from sqlalchemy import func, inspect, select

from opportunity_engine.persistence import (
    OpportunityModel,
    OpportunityRepository,
    PersistenceError,
    ShipmentEvidenceTaskModel,
    SourceRunModel,
    StatusHistoryModel,
    build_alembic_config,
    create_database_engine,
    create_session_factory,
    session_scope,
    upgrade_database,
)


ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG = ROOT / "alembic.ini"
EXPECTED_TABLES = {
    "alembic_version",
    "opportunities",
    "shipment_evidence_tasks",
    "source_runs",
    "status_history",
    "unified_opportunities",
    "unified_opportunity_evidence",
}


def _database_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'opportunity-engine.db'}"


def _opportunity(final_decision: str = "WATCH") -> dict:
    return {
        "opportunity_id": "unified-auksjonen-614288",
        "title": "4 stk komplette lagerreoler",
        "url": "https://example.test/opportunity/614288",
        "source": "auksjonen.no",
        "market_code": "NO",
        "final_decision": final_decision,
        "opportunity_score": 34.59,
        "automatic_purchase": False,
    }


def _shipment_task(status: str = "OPEN") -> dict:
    return {
        "task_id": "unified-auksjonen-614288-shipment-measurements",
        "opportunity_id": "unified-auksjonen-614288",
        "task_type": "SHIPMENT_MEASUREMENTS",
        "requested_fields": [
            "shipment.weight_kg",
            "shipment.volume_m3",
            "shipment.pallet_count",
        ],
        "source_channel": "LISTING_OR_SELLER",
        "priority": "CRITICAL",
        "status": status,
        "blocks_manual_quote": status == "OPEN",
        "blocks_qualification": status == "OPEN",
        "question_nb": "Kan dere oppgi totalvekt, volum og antall paller?",
        "question_ar": "هل يمكن تزويدنا بالوزن والحجم وعدد الطبالي؟",
        "reason": "A structured size or mass basis is required for a quote.",
        "current_value": None if status == "OPEN" else {"weight_kg": 800},
        "evidence_refs": ["seller-reply:test"],
    }


def test_alembic_upgrade_creates_expected_sqlite_schema(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path)

    upgrade_database(database_url, config_path=ALEMBIC_CONFIG)
    engine = create_database_engine(database_url)

    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES
    with engine.connect() as connection:
        foreign_keys = connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()
    assert foreign_keys == 1
    engine.dispose()


def test_repository_persists_opportunity_task_history_and_zero_run(
    tmp_path: Path,
) -> None:
    database_url = _database_url(tmp_path)
    upgrade_database(database_url, config_path=ALEMBIC_CONFIG)
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    observed_at = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)

    with session_scope(factory) as session:
        repository = OpportunityRepository(session)
        saved = repository.upsert_opportunity(
            _opportunity(),
            seen_at=observed_at,
            source_ref="data/decision_intelligence.json#unified-auksjonen-614288",
        )
        task = repository.upsert_shipment_evidence_task(
            _shipment_task(),
            source_ref="data/shipment_evidence_queue_v1.json",
        )
        run = repository.record_source_run(
            {
                "run_id": "p4-20260731T120000Z",
                "pipeline_name": "P4_DECISION_PIPELINE",
                "status": "SUCCEEDED",
                "started_at": observed_at,
                "finished_at": observed_at,
                "zero_result": True,
                "summary": {"decision_count": 0, "valid_zero_result": True},
            }
        )
        assert saved.final_decision == "WATCH"
        assert task.status == "OPEN"
        assert run.zero_result is True

    with session_scope(factory) as session:
        repository = OpportunityRepository(session)
        opportunity = repository.get_opportunity("unified-auksjonen-614288")
        task = repository.get_shipment_task(
            "unified-auksjonen-614288-shipment-measurements"
        )
        assert opportunity is not None
        assert opportunity.first_seen_at == opportunity.last_seen_at
        assert opportunity.payload_json["automatic_purchase"] is False
        assert task is not None
        assert task.requested_fields_json == [
            "shipment.weight_kg",
            "shipment.volume_m3",
            "shipment.pallet_count",
        ]
        assert task.current_value_json is None
        assert session.scalar(select(func.count()).select_from(SourceRunModel)) == 1
        assert session.scalar(select(func.count()).select_from(StatusHistoryModel)) == 2

    engine.dispose()


def test_upserts_preserve_identity_and_append_only_real_status_changes(
    tmp_path: Path,
) -> None:
    database_url = _database_url(tmp_path)
    upgrade_database(database_url, config_path=ALEMBIC_CONFIG)
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)

    with session_scope(factory) as session:
        repository = OpportunityRepository(session)
        repository.upsert_opportunity(_opportunity())
        repository.upsert_shipment_evidence_task(_shipment_task())

    with session_scope(factory) as session:
        repository = OpportunityRepository(session)
        repository.upsert_opportunity(_opportunity())
        repository.upsert_shipment_evidence_task(_shipment_task())
        assert session.scalar(select(func.count()).select_from(OpportunityModel)) == 1
        assert (
            session.scalar(select(func.count()).select_from(ShipmentEvidenceTaskModel))
            == 1
        )
        assert session.scalar(select(func.count()).select_from(StatusHistoryModel)) == 2

    resolved_task = _shipment_task("RESOLVED")
    changed_opportunity = _opportunity("BUY_REVIEW")
    with session_scope(factory) as session:
        repository = OpportunityRepository(session)
        repository.upsert_opportunity(changed_opportunity)
        repository.upsert_shipment_evidence_task(resolved_task)

    with session_scope(factory) as session:
        repository = OpportunityRepository(session)
        opportunity_history = repository.list_status_history(
            entity_type="OPPORTUNITY_DECISION",
            entity_key="unified-auksjonen-614288",
        )
        task_history = repository.list_status_history(
            entity_type="SHIPMENT_EVIDENCE_TASK",
            entity_key="unified-auksjonen-614288-shipment-measurements",
        )
        assert [(item.from_status, item.to_status) for item in opportunity_history] == [
            (None, "WATCH"),
            ("WATCH", "BUY_REVIEW"),
        ]
        assert [(item.from_status, item.to_status) for item in task_history] == [
            (None, "OPEN"),
            ("OPEN", "RESOLVED"),
        ]
        task = repository.get_shipment_task(
            "unified-auksjonen-614288-shipment-measurements"
        )
        assert task is not None
        assert task.current_value_json == {"weight_kg": 800}

    engine.dispose()


def test_task_cannot_be_persisted_before_opportunity(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path)
    upgrade_database(database_url, config_path=ALEMBIC_CONFIG)
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)

    with pytest.raises(PersistenceError, match="opportunity must be persisted"):
        with session_scope(factory) as session:
            OpportunityRepository(session).upsert_shipment_evidence_task(
                _shipment_task()
            )

    engine.dispose()


def test_repository_copies_official_values_without_recalculation(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path)
    upgrade_database(database_url, config_path=ALEMBIC_CONFIG)
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    source = _opportunity()
    source["opportunity_score"] = 91.25
    source["final_decision"] = "WATCH"

    with session_scope(factory) as session:
        model = OpportunityRepository(session).upsert_opportunity(source)
        assert model.final_decision == source["final_decision"]
        assert model.opportunity_score == source["opportunity_score"]
        assert model.payload_json == source

    engine.dispose()


def test_migration_is_reversible(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path)
    upgrade_database(database_url, config_path=ALEMBIC_CONFIG)
    config = build_alembic_config(database_url, config_path=ALEMBIC_CONFIG)

    command.downgrade(config, "base")
    engine = create_database_engine(database_url)
    remaining = set(inspect(engine).get_table_names())

    assert not ({"opportunities", "shipment_evidence_tasks", "source_runs", "status_history"} & remaining)
    engine.dispose()


def test_init_database_cli_applies_head_migration(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path)
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/init_opportunity_database.py",
            "--database-url",
            database_url,
            "--config",
            str(ALEMBIC_CONFIG),
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["revision"] == "0002_unified_opportunity_v1"
    assert set(output["tables"]) == EXPECTED_TABLES
    assert output["changes_final_decision"] is False
    assert output["changes_ranking"] is False
    assert output["changes_top5"] is False
    assert output["changes_alerts"] is False
