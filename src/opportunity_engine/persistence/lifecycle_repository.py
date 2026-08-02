"""Append-only persistence for canonical opportunity lifecycle transitions."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from .lifecycle_models import LifecycleEventModel
from .models import UnifiedOpportunityModel
from .repository import PersistenceError


LIFECYCLE_REASON_CODE_KEY = "lifecycle_reason_code"


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise PersistenceError("changed_at must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _reason_code(record_json: object) -> str | None:
    if not isinstance(record_json, Mapping):
        return None
    metadata = record_json.get("metadata")
    if not isinstance(metadata, Mapping):
        return None
    return _optional_text(metadata.get(LIFECYCLE_REASON_CODE_KEY))


@dataclass(frozen=True)
class LifecycleSnapshot:
    """The fields that define a meaningful lifecycle state."""

    listing_status: str
    evaluation_status: str
    workflow_status: str
    reason_code: str | None


class LifecycleEventRepository:
    """Record lifecycle changes once and expose append-only history."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def snapshot_from_model(
        model: UnifiedOpportunityModel | None,
    ) -> LifecycleSnapshot | None:
        if model is None:
            return None
        return LifecycleSnapshot(
            listing_status=str(model.listing_status),
            evaluation_status=str(model.evaluation_status),
            workflow_status=str(model.workflow_status),
            reason_code=_reason_code(model.record_json),
        )

    @staticmethod
    def _event_key(
        *,
        opportunity_id: str,
        previous: LifecycleSnapshot | None,
        current: LifecycleSnapshot,
        changed_at: datetime,
        source_ref: str | None,
    ) -> str:
        payload: dict[str, Any] = {
            "opportunity_id": opportunity_id,
            "previous": asdict(previous) if previous is not None else None,
            "current": asdict(current),
            "changed_at": _utc(changed_at).isoformat(),
            "source_ref": _optional_text(source_ref),
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return sha256(encoded).hexdigest()

    def record_if_changed(
        self,
        *,
        opportunity_id: str,
        previous: LifecycleSnapshot | None,
        current: LifecycleSnapshot,
        changed_at: datetime,
        source_ref: str | None = None,
    ) -> LifecycleEventModel | None:
        normalized_id = str(opportunity_id).strip()
        if not normalized_id:
            raise PersistenceError("opportunity_id must be a non-empty string")
        if previous == current:
            return None

        observed_at = _utc(changed_at)
        normalized_source = _optional_text(source_ref)
        event_key = self._event_key(
            opportunity_id=normalized_id,
            previous=previous,
            current=current,
            changed_at=observed_at,
            source_ref=normalized_source,
        )
        existing = self.session.scalar(
            select(LifecycleEventModel).where(
                LifecycleEventModel.event_key == event_key
            )
        )
        if existing is not None:
            return existing

        event = LifecycleEventModel(
            event_key=event_key,
            opportunity_id=normalized_id,
            from_listing_status=(previous.listing_status if previous else None),
            to_listing_status=current.listing_status,
            from_evaluation_status=(previous.evaluation_status if previous else None),
            to_evaluation_status=current.evaluation_status,
            from_workflow_status=(previous.workflow_status if previous else None),
            to_workflow_status=current.workflow_status,
            from_reason_code=(previous.reason_code if previous else None),
            to_reason_code=current.reason_code,
            source_ref=normalized_source,
            changed_at=observed_at,
        )
        self.session.add(event)
        self.session.flush()
        return event

    def list_for_opportunity(self, opportunity_id: str) -> list[LifecycleEventModel]:
        normalized_id = str(opportunity_id).strip()
        if not normalized_id:
            raise PersistenceError("opportunity_id must be a non-empty string")
        return list(
            self.session.scalars(
                select(LifecycleEventModel)
                .where(LifecycleEventModel.opportunity_id == normalized_id)
                .order_by(LifecycleEventModel.changed_at, LifecycleEventModel.id)
            )
        )
