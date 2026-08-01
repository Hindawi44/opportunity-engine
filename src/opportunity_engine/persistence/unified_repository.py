"""Repository boundary for canonical OpportunityRecord persistence."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from opportunity_engine.unified_models import OpportunityRecord

from .models import (
    StatusHistoryModel,
    UnifiedOpportunityEvidenceModel,
    UnifiedOpportunityModel,
    utc_now,
)
from .repository import PersistenceError


UNIFIED_WORKFLOW_ENTITY_TYPE = "UNIFIED_OPPORTUNITY_WORKFLOW"


def _utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise PersistenceError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _evidence_key(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


class UnifiedOpportunityRepository:
    """Transaction-scoped repository for canonical opportunity snapshots."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _record_workflow_change(
        self,
        *,
        opportunity_id: str,
        from_status: str | None,
        to_status: str,
        source_ref: str | None,
    ) -> None:
        self.session.add(
            StatusHistoryModel(
                entity_type=UNIFIED_WORKFLOW_ENTITY_TYPE,
                entity_key=opportunity_id,
                from_status=from_status,
                to_status=to_status,
                reason=(
                    "Initial canonical workflow snapshot."
                    if from_status is None
                    else "Canonical workflow status changed in a later snapshot."
                ),
                source_ref=_optional_text(source_ref),
                changed_at=utc_now(),
            )
        )

    def upsert_record(
        self,
        record: Mapping[str, Any],
        *,
        seen_at: datetime | None = None,
        source_ref: str | None = None,
    ) -> UnifiedOpportunityModel:
        """Insert or refresh one validated canonical record without estimation."""
        if not isinstance(record, Mapping):
            raise PersistenceError("canonical opportunity record must be an object")
        raw_record = deepcopy(dict(record))
        try:
            canonical = OpportunityRecord.model_validate(raw_record)
        except ValidationError as exc:
            raise PersistenceError(f"invalid canonical opportunity record: {exc}") from exc

        observed_at = _utc(seen_at or canonical.discovered_at, "seen_at")
        opportunity_id = canonical.opportunity_id
        model = self.session.scalar(
            select(UnifiedOpportunityModel).where(
                UnifiedOpportunityModel.opportunity_id == opportunity_id
            )
        )

        if model is None:
            model = UnifiedOpportunityModel(
                opportunity_id=opportunity_id,
                first_seen_at=observed_at,
                last_seen_at=observed_at,
            )
            self.session.add(model)
            previous_status = None
        else:
            previous_status = model.workflow_status
            first_seen = _utc(model.first_seen_at, "first_seen_at")
            last_seen = _utc(model.last_seen_at, "last_seen_at")
            model.first_seen_at = min(first_seen, observed_at)
            model.last_seen_at = max(last_seen, observed_at)

        incoming_status = canonical.workflow_status.value
        if previous_status != incoming_status:
            self._record_workflow_change(
                opportunity_id=opportunity_id,
                from_status=previous_status,
                to_status=incoming_status,
                source_ref=source_ref,
            )

        model.market_code = canonical.market_code
        model.domain = canonical.domain
        model.category = canonical.category
        model.title = canonical.title
        model.source_provider = canonical.source_provider
        model.source_url = str(canonical.source_url)
        model.listing_status = canonical.listing_status.value
        model.evaluation_status = canonical.evaluation_status.value
        model.workflow_status = incoming_status
        model.scenario = canonical.scenario
        model.company_name = canonical.company_name
        model.location = canonical.location
        model.inventory_type = canonical.inventory_type
        model.currency = canonical.currency
        model.price = canonical.price
        model.bid_price = canonical.bid_price
        model.quantity = canonical.quantity
        model.published_at = canonical.published_at
        model.discovered_at = canonical.discovered_at
        model.identity_stable = canonical.identity_stable
        model.verified = canonical.verified
        model.analysis_eligible = canonical.analysis_eligible
        model.top5_eligible = canonical.top5_eligible
        model.record_json = raw_record
        model.updated_at = utc_now()
        self.session.flush()

        for evidence in raw_record.get("evidence", []):
            if not isinstance(evidence, Mapping):
                raise PersistenceError("canonical evidence items must be objects")
            evidence_payload = deepcopy(dict(evidence))
            key = _evidence_key(evidence_payload)
            existing = self.session.scalar(
                select(UnifiedOpportunityEvidenceModel).where(
                    UnifiedOpportunityEvidenceModel.opportunity_id == opportunity_id,
                    UnifiedOpportunityEvidenceModel.evidence_key == key,
                )
            )
            if existing is not None:
                continue
            validated = next(
                item
                for item in canonical.evidence
                if _evidence_key(item.model_dump(mode="json")) == key
            )
            self.session.add(
                UnifiedOpportunityEvidenceModel(
                    opportunity_id=opportunity_id,
                    evidence_key=key,
                    evidence_type=validated.evidence_type,
                    value=validated.value,
                    source_url=(
                        str(validated.source_url)
                        if validated.source_url is not None
                        else None
                    ),
                    captured_at=validated.captured_at,
                    verified=validated.verified,
                    metadata_json=deepcopy(validated.metadata),
                )
            )

        self.session.flush()
        return model

    def get(self, opportunity_id: str) -> UnifiedOpportunityModel | None:
        normalized = str(opportunity_id).strip()
        if not normalized:
            raise PersistenceError("opportunity_id must be a non-empty string")
        return self.session.scalar(
            select(UnifiedOpportunityModel).where(
                UnifiedOpportunityModel.opportunity_id == normalized
            )
        )

    def list_evidence(
        self,
        opportunity_id: str,
    ) -> list[UnifiedOpportunityEvidenceModel]:
        normalized = str(opportunity_id).strip()
        if not normalized:
            raise PersistenceError("opportunity_id must be a non-empty string")
        return list(
            self.session.scalars(
                select(UnifiedOpportunityEvidenceModel)
                .where(UnifiedOpportunityEvidenceModel.opportunity_id == normalized)
                .order_by(UnifiedOpportunityEvidenceModel.id)
            )
        )

    def list_workflow_history(
        self,
        opportunity_id: str,
    ) -> list[StatusHistoryModel]:
        normalized = str(opportunity_id).strip()
        if not normalized:
            raise PersistenceError("opportunity_id must be a non-empty string")
        return list(
            self.session.scalars(
                select(StatusHistoryModel)
                .where(
                    StatusHistoryModel.entity_type == UNIFIED_WORKFLOW_ENTITY_TYPE,
                    StatusHistoryModel.entity_key == normalized,
                )
                .order_by(StatusHistoryModel.id)
            )
        )
