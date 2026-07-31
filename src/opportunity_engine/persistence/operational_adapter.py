"""Persist operational JSON snapshots through the repository boundary.

The adapter copies one selected opportunity and its shipment-evidence tasks into
SQLite without recalculating decisions, scores, rankings, or workflow outputs.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from .repository import OpportunityRepository, PersistenceError


PIPELINE_NAME = "P4_OPERATIONAL_PERSISTENCE_V1"


class OperationalPersistenceError(PersistenceError):
    """Raised when operational snapshots are incomplete or inconsistent."""


def _object(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OperationalPersistenceError(f"{field_name} must be an object")
    return value


def _list(value: object, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise OperationalPersistenceError(f"{field_name} must be a list")
    return value


def _string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OperationalPersistenceError(f"{field_name} must be a non-empty string")
    return value.strip()


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise OperationalPersistenceError(f"{field_name} must be a non-negative integer")
    return value


def _optional_number(value: object, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OperationalPersistenceError(f"{field_name} must be null or numeric")
    return float(value)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _decision_index(decision_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    decisions = _list(decision_payload.get("decisions"), "decisions")
    declared_count = decision_payload.get("decision_count", len(decisions))
    if _integer(declared_count, "decision_count") != len(decisions):
        raise OperationalPersistenceError("decision_count does not match decisions")

    index: dict[str, dict[str, Any]] = {}
    for position, raw_record in enumerate(decisions):
        record = _object(raw_record, f"decisions[{position}]")
        opportunity_id = _string(
            record.get("opportunity_id"), f"decisions[{position}].opportunity_id"
        )
        if opportunity_id in index:
            raise OperationalPersistenceError(
                f"duplicate opportunity_id in decisions: {opportunity_id}"
            )
        index[opportunity_id] = record
    return index


def _validate_queue_counts(queue_payload: dict[str, Any], tasks: list[Any]) -> None:
    declared_count = queue_payload.get("task_count", len(tasks))
    if _integer(declared_count, "task_count") != len(tasks):
        raise OperationalPersistenceError("task_count does not match tasks")

    blocking_count = 0
    seen_task_ids: set[str] = set()
    for position, raw_task in enumerate(tasks):
        task = _object(raw_task, f"tasks[{position}]")
        task_id = _string(task.get("task_id"), f"tasks[{position}].task_id")
        if task_id in seen_task_ids:
            raise OperationalPersistenceError(f"duplicate task_id in queue: {task_id}")
        seen_task_ids.add(task_id)
        blocks = task.get("blocks_manual_quote")
        if not isinstance(blocks, bool):
            raise OperationalPersistenceError(
                f"tasks[{position}].blocks_manual_quote must be boolean"
            )
        blocking_count += int(blocks)

    declared_blocking = queue_payload.get("blocking_task_count", blocking_count)
    if _integer(declared_blocking, "blocking_task_count") != blocking_count:
        raise OperationalPersistenceError(
            "blocking_task_count does not match blocking tasks"
        )


def _validate_source_copy(
    source: dict[str, Any],
    decision: dict[str, Any],
    opportunity_id: str,
) -> None:
    source_decision = source.get("final_decision")
    decision_value = decision.get("final_decision")
    if source_decision is not None and source_decision != decision_value:
        raise OperationalPersistenceError(
            "shipment queue final_decision does not match decision_intelligence"
        )

    source_score = _optional_number(
        source.get("opportunity_score"), "source_opportunity.opportunity_score"
    )
    decision_score = _optional_number(
        decision.get("opportunity_score"), "decision.opportunity_score"
    )
    if source_score is not None and source_score != decision_score:
        raise OperationalPersistenceError(
            "shipment queue opportunity_score does not match decision_intelligence"
        )

    if _string(source.get("opportunity_id"), "source_opportunity.opportunity_id") != opportunity_id:
        raise OperationalPersistenceError("source opportunity identity mismatch")


def persist_operational_snapshots(
    decision_payload: dict[str, Any],
    shipment_queue_payload: dict[str, Any],
    repository: OpportunityRepository,
    *,
    run_id: str,
    started_at: datetime,
    finished_at: datetime | None = None,
    market_code: str = "NO",
    decision_source_ref: str = "data/decision_intelligence.json",
    queue_source_ref: str = "data/shipment_evidence_queue_v1.json",
) -> dict[str, Any]:
    """Persist one operational selection and its tasks in the current transaction."""
    decisions_root = _object(decision_payload, "decision_payload")
    queue_root = _object(shipment_queue_payload, "shipment_queue_payload")
    if not isinstance(repository, OpportunityRepository):
        raise OperationalPersistenceError("repository must be OpportunityRepository")
    if not isinstance(started_at, datetime):
        raise OperationalPersistenceError("started_at must be a datetime")
    completed_at = finished_at or _utc_now()
    if not isinstance(completed_at, datetime):
        raise OperationalPersistenceError("finished_at must be a datetime")
    if completed_at < started_at:
        raise OperationalPersistenceError("finished_at must not be before started_at")

    normalized_run_id = _string(run_id, "run_id")
    normalized_market = _string(market_code, "market_code").upper()
    index = _decision_index(decisions_root)
    selection_status = _string(queue_root.get("selection_status"), "selection_status")
    tasks = _list(queue_root.get("tasks", []), "tasks")
    _validate_queue_counts(queue_root, tasks)

    persisted_opportunity_id: str | None = None
    persisted_task_ids: list[str] = []

    if selection_status == "NO_ELIGIBLE_OPPORTUNITY":
        if queue_root.get("source_opportunity") is not None or tasks:
            raise OperationalPersistenceError(
                "zero selection must not contain a source opportunity or tasks"
            )
    elif selection_status == "SELECTED":
        source = _object(queue_root.get("source_opportunity"), "source_opportunity")
        opportunity_id = _string(
            source.get("opportunity_id"), "source_opportunity.opportunity_id"
        )
        decision = index.get(opportunity_id)
        if decision is None:
            raise OperationalPersistenceError(
                "selected opportunity is missing from decision_intelligence"
            )
        _validate_source_copy(source, decision, opportunity_id)

        record = deepcopy(decision)
        existing_market = record.get("market_code")
        if existing_market is not None and existing_market != normalized_market:
            raise OperationalPersistenceError(
                "decision market_code conflicts with adapter market_code"
            )
        record["market_code"] = normalized_market
        repository.upsert_opportunity(
            record,
            source_ref=f"{decision_source_ref}#{opportunity_id}",
        )
        persisted_opportunity_id = opportunity_id

        for position, raw_task in enumerate(tasks):
            task = _object(raw_task, f"tasks[{position}]")
            task_opportunity_id = _string(
                task.get("opportunity_id"), f"tasks[{position}].opportunity_id"
            )
            if task_opportunity_id != opportunity_id:
                raise OperationalPersistenceError(
                    "shipment task belongs to a different opportunity"
                )
            task_id = _string(task.get("task_id"), f"tasks[{position}].task_id")
            repository.upsert_shipment_evidence_task(
                task,
                source_ref=f"{queue_source_ref}#{task_id}",
            )
            persisted_task_ids.append(task_id)
    else:
        raise OperationalPersistenceError(
            "selection_status must be SELECTED or NO_ELIGIBLE_OPPORTUNITY"
        )

    workflow_status = queue_root.get("workflow_status")
    if workflow_status is not None:
        workflow_status = _string(workflow_status, "workflow_status")

    repository.record_source_run(
        {
            "run_id": normalized_run_id,
            "pipeline_name": PIPELINE_NAME,
            "status": "SUCCESS",
            "started_at": started_at,
            "finished_at": completed_at,
            "zero_result": persisted_opportunity_id is None,
            "summary": {
                "decision_count": len(index),
                "selection_status": selection_status,
                "workflow_status": workflow_status,
                "persisted_opportunity_id": persisted_opportunity_id,
                "persisted_task_count": len(persisted_task_ids),
                "persisted_task_ids": persisted_task_ids,
                "decision_source_ref": decision_source_ref,
                "queue_source_ref": queue_source_ref,
            },
        }
    )

    return {
        "run_id": normalized_run_id,
        "pipeline_name": PIPELINE_NAME,
        "selection_status": selection_status,
        "workflow_status": workflow_status,
        "persisted_opportunity_id": persisted_opportunity_id,
        "persisted_task_count": len(persisted_task_ids),
        "persisted_task_ids": persisted_task_ids,
        "zero_result": persisted_opportunity_id is None,
        "scope": {
            "json_reports_remain_official": True,
            "changes_final_decision": False,
            "changes_scoring": False,
            "changes_ranking": False,
            "changes_top5": False,
            "changes_alerts": False,
            "automatic_task_resolution": False,
        },
    }
