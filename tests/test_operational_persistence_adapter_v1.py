from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import func, select

from opportunity_engine.buyers import BuyerProfileV1
from opportunity_engine.costs import build_operational_landed_cost_export
from opportunity_engine.logistics import (
    build_operational_transport_export,
    build_shipment_evidence_queue,
)
from opportunity_engine.markets import MarketProfileV1
from opportunity_engine.persistence import (
    OperationalPersistenceError,
    OpportunityModel,
    OpportunityRepository,
    ShipmentEvidenceTaskModel,
    SourceRunModel,
    StatusHistoryModel,
    create_database_engine,
    create_session_factory,
    persist_operational_snapshots,
    session_scope,
    upgrade_database,
)


ROOT = Path(__file__).resolve().parents[1]
DECISIONS_PATH = ROOT / "data" / "decision_intelligence.json"
BUYER_PATH = ROOT / "config" / "buyers" / "mahmoud_namsos_v1.json"
MARKET_PATH = ROOT / "config" / "markets" / "no_v1.json"
ALEMBIC_CONFIG = ROOT / "alembic.ini"
NOW = datetime(2026, 7, 31, 13, 0, tzinfo=timezone.utc)


def _decisions() -> dict:
    return json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))


def _operational_queue(decisions: dict | None = None) -> dict:
    decision_payload = decisions or _decisions()
    buyer = BuyerProfileV1.from_path(BUYER_PATH)
    market = MarketProfileV1.from_path(MARKET_PATH)
    landed = build_operational_landed_cost_export(decision_payload, buyer)
    transport = build_operational_transport_export(landed, buyer, market)
    return build_shipment_evidence_queue(transport)


def _database(tmp_path: Path):
    database_url = f"sqlite:///{tmp_path / 'operational-state.db'}"
    upgrade_database(database_url, config_path=ALEMBIC_CONFIG)
    engine = create_database_engine(database_url)
    return database_url, engine, create_session_factory(engine)


def test_real_operational_snapshots_persist_exact_decision_and_tasks(
    tmp_path: Path,
) -> None:
    decisions = _decisions()
    queue = _operational_queue(decisions)
    _database_url, engine, factory = _database(tmp_path)
    try:
        with session_scope(factory) as session:
            summary = persist_operational_snapshots(
                decisions,
                queue,
                OpportunityRepository(session),
                run_id="real-operational-run",
                started_at=NOW,
                finished_at=NOW,
            )

        selected_id = queue["source_opportunity"]["opportunity_id"]
        official = next(
            item for item in decisions["decisions"]
            if item["opportunity_id"] == selected_id
        )
        assert summary["persisted_opportunity_id"] == selected_id
        assert summary["persisted_task_count"] == queue["task_count"]
        assert summary["scope"]["json_reports_remain_official"] is True
        assert summary["scope"]["changes_final_decision"] is False

        with factory() as session:
            opportunity = session.scalar(
                select(OpportunityModel).where(
                    OpportunityModel.opportunity_id == selected_id
                )
            )
            assert opportunity is not None
            assert opportunity.final_decision == official["final_decision"]
            assert opportunity.opportunity_score == official["opportunity_score"]
            assert opportunity.payload_json["final_decision"] == official["final_decision"]
            assert opportunity.market_code == "NO"

            tasks = list(
                session.scalars(
                    select(ShipmentEvidenceTaskModel)
                    .where(ShipmentEvidenceTaskModel.opportunity_id == selected_id)
                    .order_by(ShipmentEvidenceTaskModel.task_id)
                )
            )
            assert len(tasks) == queue["task_count"]
            assert {task.task_id for task in tasks} == {
                task["task_id"] for task in queue["tasks"]
            }
            assert all(task.status == "OPEN" for task in tasks)

            run = session.scalar(
                select(SourceRunModel).where(
                    SourceRunModel.run_id == "real-operational-run"
                )
            )
            assert run is not None
            assert run.zero_result is False
            assert run.summary_json["persisted_opportunity_id"] == selected_id
            assert run.summary_json["persisted_task_count"] == queue["task_count"]
    finally:
        engine.dispose()


def test_replaying_same_snapshot_does_not_duplicate_status_history(
    tmp_path: Path,
) -> None:
    decisions = _decisions()
    queue = _operational_queue(decisions)
    _database_url, engine, factory = _database(tmp_path)
    selected_id = queue["source_opportunity"]["opportunity_id"]
    try:
        for run_id in ("replay-1", "replay-2"):
            with session_scope(factory) as session:
                persist_operational_snapshots(
                    decisions,
                    queue,
                    OpportunityRepository(session),
                    run_id=run_id,
                    started_at=NOW,
                    finished_at=NOW,
                )

        with factory() as session:
            decision_history_count = session.scalar(
                select(func.count(StatusHistoryModel.id)).where(
                    StatusHistoryModel.entity_type == "OPPORTUNITY_DECISION",
                    StatusHistoryModel.entity_key == selected_id,
                )
            )
            task_history_count = session.scalar(
                select(func.count(StatusHistoryModel.id)).where(
                    StatusHistoryModel.entity_type == "SHIPMENT_EVIDENCE_TASK"
                )
            )
            run_count = session.scalar(select(func.count(SourceRunModel.id)))
            assert decision_history_count == 1
            assert task_history_count == queue["task_count"]
            assert run_count == 2
    finally:
        engine.dispose()


def test_invalid_task_rolls_back_the_whole_operational_transaction(
    tmp_path: Path,
) -> None:
    decisions = _decisions()
    queue = deepcopy(_operational_queue(decisions))
    queue["tasks"][0]["opportunity_id"] = "another-opportunity"
    _database_url, engine, factory = _database(tmp_path)
    try:
        with pytest.raises(
            OperationalPersistenceError,
            match="different opportunity",
        ):
            with session_scope(factory) as session:
                persist_operational_snapshots(
                    decisions,
                    queue,
                    OpportunityRepository(session),
                    run_id="rollback-run",
                    started_at=NOW,
                    finished_at=NOW,
                )

        with factory() as session:
            assert session.scalar(select(func.count(OpportunityModel.id))) == 0
            assert session.scalar(select(func.count(ShipmentEvidenceTaskModel.id))) == 0
            assert session.scalar(select(func.count(SourceRunModel.id))) == 0
            assert session.scalar(select(func.count(StatusHistoryModel.id))) == 0
    finally:
        engine.dispose()


def test_queue_decision_copy_must_match_official_decision(tmp_path: Path) -> None:
    decisions = _decisions()
    queue = deepcopy(_operational_queue(decisions))
    queue["source_opportunity"]["final_decision"] = "BUY"
    _database_url, engine, factory = _database(tmp_path)
    try:
        with pytest.raises(OperationalPersistenceError, match="final_decision"):
            with session_scope(factory) as session:
                persist_operational_snapshots(
                    decisions,
                    queue,
                    OpportunityRepository(session),
                    run_id="mismatch-run",
                    started_at=NOW,
                    finished_at=NOW,
                )
    finally:
        engine.dispose()


def test_zero_selection_persists_a_valid_zero_result_run(tmp_path: Path) -> None:
    decisions = {"decision_count": 0, "decisions": []}
    queue = _operational_queue(decisions)
    assert queue["selection_status"] == "NO_ELIGIBLE_OPPORTUNITY"
    _database_url, engine, factory = _database(tmp_path)
    try:
        with session_scope(factory) as session:
            summary = persist_operational_snapshots(
                decisions,
                queue,
                OpportunityRepository(session),
                run_id="zero-run",
                started_at=NOW,
                finished_at=NOW,
            )
        assert summary["zero_result"] is True
        assert summary["persisted_opportunity_id"] is None
        assert summary["persisted_task_count"] == 0

        with factory() as session:
            assert session.scalar(select(func.count(OpportunityModel.id))) == 0
            run = session.scalar(
                select(SourceRunModel).where(SourceRunModel.run_id == "zero-run")
            )
            assert run is not None
            assert run.zero_result is True
            assert run.summary_json["selection_status"] == (
                "NO_ELIGIBLE_OPPORTUNITY"
            )
    finally:
        engine.dispose()


def test_cli_migrates_and_persists_real_operational_snapshots(
    tmp_path: Path,
) -> None:
    decisions_path = tmp_path / "decisions.json"
    queue_path = tmp_path / "shipment-queue.json"
    database_path = tmp_path / "cli-state.db"
    decisions = _decisions()
    queue = _operational_queue(decisions)
    decisions_path.write_text(
        json.dumps(decisions, ensure_ascii=False), encoding="utf-8"
    )
    queue_path.write_text(json.dumps(queue, ensure_ascii=False), encoding="utf-8")

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [
            sys.executable,
            "scripts/persist_operational_state.py",
            "--decisions",
            str(decisions_path),
            "--shipment-evidence",
            str(queue_path),
            "--database-url",
            f"sqlite:///{database_path}",
            "--alembic-config",
            str(ALEMBIC_CONFIG),
            "--run-id",
            "cli-operational-run",
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    printed = json.loads(result.stdout)
    assert printed["run_id"] == "cli-operational-run"
    assert printed["persisted_task_count"] == queue["task_count"]
    assert database_path.exists()

    engine = create_database_engine(f"sqlite:///{database_path}")
    try:
        factory = create_session_factory(engine)
        with factory() as session:
            assert session.scalar(select(func.count(OpportunityModel.id))) == 1
            assert session.scalar(
                select(func.count(ShipmentEvidenceTaskModel.id))
            ) == queue["task_count"]
            assert session.scalar(select(func.count(SourceRunModel.id))) == 1
    finally:
        engine.dispose()
