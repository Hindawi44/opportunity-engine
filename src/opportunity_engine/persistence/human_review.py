"""Apply explicit human review outcomes to canonical opportunity lifecycle state."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
import json
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from .human_review_models import HumanReviewOutcomeModel
from .lifecycle_repository import LifecycleEventRepository
from .repository import PersistenceError
from .unified_repository import UnifiedOpportunityRepository


class HumanReviewOutcome(StrEnum):
    VERIFIED = "VERIFIED"
    NEEDS_MORE_INFORMATION = "NEEDS_MORE_INFORMATION"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"


_REASON_BY_OUTCOME = {
    HumanReviewOutcome.VERIFIED: "HUMAN_REVIEW_VERIFIED",
    HumanReviewOutcome.NEEDS_MORE_INFORMATION: "HUMAN_REVIEW_NEEDS_MORE_INFORMATION",
    HumanReviewOutcome.REJECTED: "HUMAN_REVIEW_REJECTED",
    HumanReviewOutcome.CLOSED: "HUMAN_REVIEW_CLOSED",
}
_INACTIVE_LISTING_STATUSES = {"ENDED", "SOLD", "UNAVAILABLE"}
_EXACT_ITEM_PAGE_BLOCKER = "verified exact item-page evidence"


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise PersistenceError("reviewed_at must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _text(value: object) -> str | None:
    if value is None:
        return None
    compact = " ".join(str(value).split())
    return compact or None


def _review_key(
    *,
    opportunity_id: str,
    outcome: HumanReviewOutcome,
    reviewed_at: datetime,
    reviewer: str | None,
    note: str | None,
    source_ref: str | None,
    request_id: str | None,
) -> str:
    payload = {
        "request_id": _text(request_id),
        "opportunity_id": opportunity_id,
        "outcome": outcome.value,
        "reviewed_at": _utc(reviewed_at).isoformat(),
        "reviewer": _text(reviewer),
        "note": _text(note),
        "source_ref": _text(source_ref),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _metadata(record: dict[str, Any]) -> dict[str, Any]:
    raw = record.get("metadata")
    metadata = deepcopy(dict(raw)) if isinstance(raw, Mapping) else {}
    record["metadata"] = metadata
    return metadata


def _missing_names(record: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    for raw in record.get("missing_information") or []:
        if isinstance(raw, Mapping):
            value = _text(raw.get("field_name"))
        else:
            value = _text(raw)
        if value:
            result.append(value)
    return result


def _without_exact_page_blocker(record: dict[str, Any]) -> list[dict[str, Any]]:
    remaining: list[dict[str, Any]] = []
    for raw in record.get("missing_information") or []:
        if isinstance(raw, Mapping):
            item = deepcopy(dict(raw))
            name = _text(item.get("field_name"))
        else:
            name = _text(raw)
            item = {"field_name": name} if name else {}
        if not name or name == _EXACT_ITEM_PAGE_BLOCKER:
            continue
        remaining.append(item)
    return remaining


def _append_review_evidence(
    record: dict[str, Any],
    review: HumanReviewOutcomeModel,
) -> None:
    evidence = record.get("evidence")
    values = deepcopy(evidence) if isinstance(evidence, list) else []
    values.append(
        {
            "evidence_type": "HUMAN_REVIEW",
            "value": review.note
            or f"Human review outcome recorded: {review.outcome}.",
            "source_url": None,
            "captured_at": _utc(review.reviewed_at).isoformat(),
            "verified": review.outcome == HumanReviewOutcome.VERIFIED.value,
            "metadata": {
                "outcome": review.outcome,
                "reviewer": review.reviewer,
                "review_key": review.review_key,
                "source_ref": review.source_ref,
            },
        }
    )
    record["evidence"] = values


def apply_persisted_human_review(
    raw_record: Mapping[str, Any],
    review: HumanReviewOutcomeModel | None,
) -> dict[str, Any]:
    """Overlay the latest human decision without overriding true source closure."""
    record = deepcopy(dict(raw_record))
    if review is None:
        return record

    metadata = _metadata(record)
    metadata["human_review"] = {
        "outcome": review.outcome,
        "reviewer": review.reviewer,
        "note": review.note,
        "reviewed_at": _utc(review.reviewed_at).isoformat(),
        "review_key": review.review_key,
        "source_ref": review.source_ref,
    }

    listing_status = str(record.get("listing_status") or "UNKNOWN").upper()
    if listing_status in _INACTIVE_LISTING_STATUSES:
        return record

    outcome = HumanReviewOutcome(review.outcome)
    metadata["lifecycle_reason_code"] = _REASON_BY_OUTCOME[outcome]
    _append_review_evidence(record, review)

    if outcome is HumanReviewOutcome.VERIFIED:
        remaining = _without_exact_page_blocker(record)
        record["missing_information"] = remaining
        record["verified"] = True
        if remaining:
            record["evaluation_status"] = "REQUIRES_VERIFICATION"
            record["workflow_status"] = "REQUIRES_VERIFICATION"
            record["analysis_eligible"] = False
            metadata["lifecycle_reason_code"] = (
                "HUMAN_REVIEW_VERIFIED_MORE_INFORMATION_REQUIRED"
            )
        else:
            record["evaluation_status"] = "NOT_EVALUATED"
            record["workflow_status"] = "ACTIVE_OPPORTUNITY"
            record["analysis_eligible"] = True
        return record

    if outcome is HumanReviewOutcome.NEEDS_MORE_INFORMATION:
        record["verified"] = False
        record["evaluation_status"] = "REQUIRES_VERIFICATION"
        record["workflow_status"] = "REQUIRES_VERIFICATION"
        record["analysis_eligible"] = False
        return record

    if outcome is HumanReviewOutcome.REJECTED:
        record["verified"] = False
        record["evaluation_status"] = "REJECTED"
        record["workflow_status"] = "REJECTED"
        record["analysis_eligible"] = False
        record["top5_eligible"] = False
        return record

    record["listing_status"] = "UNAVAILABLE"
    record["verified"] = False
    record["evaluation_status"] = "REQUIRES_VERIFICATION"
    record["workflow_status"] = "CLOSED"
    record["analysis_eligible"] = False
    record["top5_eligible"] = False
    return record


class HumanReviewOutcomeRepository:
    """Append review decisions and expose the latest decision per opportunity."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def latest_for_opportunity(
        self, opportunity_id: str
    ) -> HumanReviewOutcomeModel | None:
        normalized = str(opportunity_id).strip()
        if not normalized:
            raise PersistenceError("opportunity_id must be a non-empty string")
        return self.session.scalar(
            select(HumanReviewOutcomeModel)
            .where(HumanReviewOutcomeModel.opportunity_id == normalized)
            .order_by(
                HumanReviewOutcomeModel.reviewed_at.desc(),
                HumanReviewOutcomeModel.id.desc(),
            )
            .limit(1)
        )

    def record(
        self,
        *,
        opportunity_id: str,
        outcome: HumanReviewOutcome | str,
        reviewed_at: datetime,
        reviewer: str | None = None,
        note: str | None = None,
        source_ref: str | None = None,
        request_id: str | None = None,
    ) -> HumanReviewOutcomeModel:
        normalized_id = str(opportunity_id).strip()
        if not normalized_id:
            raise PersistenceError("opportunity_id must be a non-empty string")
        normalized_outcome = HumanReviewOutcome(str(outcome).upper())
        observed_at = _utc(reviewed_at)
        key = _review_key(
            opportunity_id=normalized_id,
            outcome=normalized_outcome,
            reviewed_at=observed_at,
            reviewer=reviewer,
            note=note,
            source_ref=source_ref,
            request_id=request_id,
        )
        existing = self.session.scalar(
            select(HumanReviewOutcomeModel).where(
                HumanReviewOutcomeModel.review_key == key
            )
        )
        if existing is not None:
            return existing
        model = HumanReviewOutcomeModel(
            review_key=key,
            opportunity_id=normalized_id,
            outcome=normalized_outcome.value,
            reviewer=_text(reviewer),
            note=_text(note),
            source_ref=_text(source_ref),
            reviewed_at=observed_at,
        )
        self.session.add(model)
        self.session.flush()
        return model


def apply_human_review_outcome(
    repository: UnifiedOpportunityRepository,
    *,
    opportunity_id: str,
    outcome: HumanReviewOutcome | str,
    reviewed_at: datetime,
    reviewer: str | None = None,
    note: str | None = None,
    source_ref: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Persist one review, update current state, and append one real transition."""
    model = repository.get(opportunity_id)
    if model is None:
        raise PersistenceError(f"unknown opportunity_id: {opportunity_id}")

    review_repository = HumanReviewOutcomeRepository(repository.session)
    lifecycle_repository = LifecycleEventRepository(repository.session)
    previous = lifecycle_repository.snapshot_from_model(model)
    review = review_repository.record(
        opportunity_id=opportunity_id,
        outcome=outcome,
        reviewed_at=reviewed_at,
        reviewer=reviewer,
        note=note,
        source_ref=source_ref,
        request_id=request_id,
    )
    effective = apply_persisted_human_review(model.record_json, review)
    saved = repository.upsert_record(
        effective,
        seen_at=reviewed_at,
        source_ref=source_ref or f"human-review:{review.review_key}",
    )
    current = lifecycle_repository.snapshot_from_model(saved)
    if current is None:
        raise PersistenceError("human review produced no lifecycle snapshot")
    event = lifecycle_repository.record_if_changed(
        opportunity_id=opportunity_id,
        previous=previous,
        current=current,
        changed_at=reviewed_at,
        source_ref=source_ref or f"human-review:{review.review_key}",
    )
    return {
        "schema_version": "human-review-outcome-1.0",
        "opportunity_id": opportunity_id,
        "outcome": review.outcome,
        "reviewer": review.reviewer,
        "note": review.note,
        "reviewed_at": _utc(review.reviewed_at).isoformat(),
        "review_key": review.review_key,
        "listing_status": saved.listing_status,
        "evaluation_status": saved.evaluation_status,
        "workflow_status": saved.workflow_status,
        "verified": bool(saved.verified),
        "analysis_eligible": bool(saved.analysis_eligible),
        "top5_eligible": bool(saved.top5_eligible),
        "remaining_missing_information": _missing_names(saved.record_json),
        "lifecycle_transition_created": event is not None and previous != current,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
