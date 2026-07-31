"""Repository boundary for durable opportunity and workflow state."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    OpportunityModel,
    ShipmentEvidenceTaskModel,
    SourceRunModel,
    StatusHistoryModel,
)


class PersistenceError(ValueError):
    """Raised when a persistence command is incomplete or inconsistent."""


def _required_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersistenceError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _required_string(value, field_name)


def _optional_number(value: object, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PersistenceError(f"{field_name} must be null or numeric")
    return float(value)


def _required_bool(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise PersistenceError(f"{field_name} must be boolean")
    return value


def _required_string_list(value: object, field_name: str) -> list[str]:
    if not isinstance(value, (list, tuple)):
        raise PersistenceError(f"{field_name} must be a list")
    result = [_required_string(item, f"{field_name}[]") for item in value]
    if len(set(result)) != len(result):
        raise PersistenceError(f"{field_name} must not contain duplicates")
    return result


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OpportunityRepository:
    """Transaction-scoped repository over SQLAlchemy models."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _record_status(
        self,
        *,
        entity_type: str,
        entity_key: str,
        from_status: str | None,
        to_status: str,
        reason: str | None = None,
        source_ref: str | None = None,
    ) -> StatusHistoryModel:
        entry = StatusHistoryModel(
            entity_type=_required_string(entity_type, "entity_type"),
            entity_key=_required_string(entity_key, "entity_key"),
            from_status=_optional_string(from_status, "from_status"),
            to_status=_required_string(to_status, "to_status"),
            reason=_optional_string(reason, "reason"),
            source_ref=_optional_string(source_ref, "source_ref"),
            changed_at=_utc_now(),
        )
        self.session.add(entry)
        return entry

    def upsert_opportunity(
        self,
        record: dict[str, Any],
        *,
        seen_at: datetime | None = None,
        source_ref: str | None = None,
    ) -> OpportunityModel:
        """Insert or refresh an opportunity without recalculating its decision."""
        if not isinstance(record, dict):
            raise PersistenceError("opportunity record must be an object")
        opportunity_id = _required_string(record.get("opportunity_id"), "opportunity_id")
        observed_at = seen_at or _utc_now()
        model = self.session.scalar(
            select(OpportunityModel).where(
                OpportunityModel.opportunity_id == opportunity_id
            )
        )
        incoming_decision = _optional_string(record.get("final_decision"), "final_decision")

        if model is None:
            model = OpportunityModel(
                opportunity_id=opportunity_id,
                first_seen_at=observed_at,
                last_seen_at=observed_at,
            )
            self.session.add(model)
            if incoming_decision is not None:
                self._record_status(
                    entity_type="OPPORTUNITY_DECISION",
                    entity_key=opportunity_id,
                    from_status=None,
                    to_status=incoming_decision,
                    reason="Initial persisted decision snapshot.",
                    source_ref=source_ref,
                )
        elif model.final_decision != incoming_decision and incoming_decision is not None:
            self._record_status(
                entity_type="OPPORTUNITY_DECISION",
                entity_key=opportunity_id,
                from_status=model.final_decision,
                to_status=incoming_decision,
                reason="Decision value changed in a later source snapshot.",
                source_ref=source_ref,
            )

        model.title = _optional_string(record.get("title"), "title")
        model.url = _optional_string(record.get("url"), "url")
        model.source = _optional_string(record.get("source"), "source")
        model.market_code = _optional_string(record.get("market_code"), "market_code")
        model.final_decision = incoming_decision
        model.opportunity_score = _optional_number(
            record.get("opportunity_score"), "opportunity_score"
        )
        model.payload_json = deepcopy(record)
        model.last_seen_at = observed_at
        model.updated_at = _utc_now()
        self.session.flush()
        return model

    def get_opportunity(self, opportunity_id: str) -> OpportunityModel | None:
        return self.session.scalar(
            select(OpportunityModel).where(
                OpportunityModel.opportunity_id
                == _required_string(opportunity_id, "opportunity_id")
            )
        )

    def upsert_shipment_evidence_task(
        self,
        task: dict[str, Any],
        *,
        source_ref: str | None = None,
    ) -> ShipmentEvidenceTaskModel:
        """Insert or refresh one task and append any status transition."""
        if not isinstance(task, dict):
            raise PersistenceError("shipment evidence task must be an object")
        task_id = _required_string(task.get("task_id"), "task_id")
        opportunity_id = _required_string(task.get("opportunity_id"), "opportunity_id")
        if self.get_opportunity(opportunity_id) is None:
            raise PersistenceError(
                "opportunity must be persisted before its shipment evidence tasks"
            )

        incoming_status = _required_string(task.get("status"), "status")
        model = self.session.scalar(
            select(ShipmentEvidenceTaskModel).where(
                ShipmentEvidenceTaskModel.task_id == task_id
            )
        )
        if model is None:
            model = ShipmentEvidenceTaskModel(
                task_id=task_id,
                opportunity_id=opportunity_id,
            )
            self.session.add(model)
            self._record_status(
                entity_type="SHIPMENT_EVIDENCE_TASK",
                entity_key=task_id,
                from_status=None,
                to_status=incoming_status,
                reason="Initial persisted shipment evidence task.",
                source_ref=source_ref,
            )
        else:
            if model.opportunity_id != opportunity_id:
                raise PersistenceError("task_id cannot move to another opportunity")
            if model.status != incoming_status:
                self._record_status(
                    entity_type="SHIPMENT_EVIDENCE_TASK",
                    entity_key=task_id,
                    from_status=model.status,
                    to_status=incoming_status,
                    reason="Task status changed in a later workflow snapshot.",
                    source_ref=source_ref,
                )

        model.task_type = _required_string(task.get("task_type"), "task_type")
        model.requested_fields_json = _required_string_list(
            task.get("requested_fields"), "requested_fields"
        )
        model.priority = _required_string(task.get("priority"), "priority")
        model.status = incoming_status
        model.source_channel = _required_string(
            task.get("source_channel"), "source_channel"
        )
        model.question_nb = _required_string(task.get("question_nb"), "question_nb")
        model.question_ar = _required_string(task.get("question_ar"), "question_ar")
        model.reason = _required_string(task.get("reason"), "reason")
        model.current_value_json = deepcopy(task.get("current_value"))
        model.blocks_manual_quote = _required_bool(
            task.get("blocks_manual_quote"), "blocks_manual_quote"
        )
        model.blocks_qualification = _required_bool(
            task.get("blocks_qualification"), "blocks_qualification"
        )
        model.evidence_refs_json = _required_string_list(
            task.get("evidence_refs", []), "evidence_refs"
        )
        model.payload_json = deepcopy(task)
        model.updated_at = _utc_now()
        self.session.flush()
        return model

    def get_shipment_task(self, task_id: str) -> ShipmentEvidenceTaskModel | None:
        return self.session.scalar(
            select(ShipmentEvidenceTaskModel).where(
                ShipmentEvidenceTaskModel.task_id
                == _required_string(task_id, "task_id")
            )
        )

    def record_source_run(self, run: dict[str, Any]) -> SourceRunModel:
        """Persist a successful, failed, or valid zero-result pipeline run."""
        if not isinstance(run, dict):
            raise PersistenceError("source run must be an object")
        run_id = _required_string(run.get("run_id"), "run_id")
        model = self.session.scalar(
            select(SourceRunModel).where(SourceRunModel.run_id == run_id)
        )
        if model is None:
            model = SourceRunModel(run_id=run_id)
            self.session.add(model)

        started_at = run.get("started_at")
        finished_at = run.get("finished_at")
        if not isinstance(started_at, datetime):
            raise PersistenceError("started_at must be a datetime")
        if finished_at is not None and not isinstance(finished_at, datetime):
            raise PersistenceError("finished_at must be null or a datetime")

        model.pipeline_name = _required_string(run.get("pipeline_name"), "pipeline_name")
        model.status = _required_string(run.get("status"), "status")
        model.started_at = started_at
        model.finished_at = finished_at
        model.zero_result = _required_bool(run.get("zero_result"), "zero_result")
        summary = run.get("summary", {})
        if not isinstance(summary, dict):
            raise PersistenceError("summary must be an object")
        model.summary_json = deepcopy(summary)
        model.updated_at = _utc_now()
        self.session.flush()
        return model

    def list_status_history(
        self,
        *,
        entity_type: str,
        entity_key: str,
    ) -> list[StatusHistoryModel]:
        return list(
            self.session.scalars(
                select(StatusHistoryModel)
                .where(
                    StatusHistoryModel.entity_type
                    == _required_string(entity_type, "entity_type"),
                    StatusHistoryModel.entity_key
                    == _required_string(entity_key, "entity_key"),
                )
                .order_by(StatusHistoryModel.id)
            )
        )
