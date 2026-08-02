"""Persist unified-opportunity-report.json through the canonical repository."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from .lifecycle_repository import LifecycleEventRepository
from .repository import PersistenceError
from .unified_repository import UnifiedOpportunityRepository


UNIFIED_REPORT_SCHEMA_VERSION = "1.1"
SUPPORTED_UNIFIED_REPORT_SCHEMA_VERSIONS = frozenset({"1.0", UNIFIED_REPORT_SCHEMA_VERSION})


class UnifiedReportPersistenceError(PersistenceError):
    """Raised when a unified report envelope is inconsistent."""


def _list(value: object, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise UnifiedReportPersistenceError(f"{field_name} must be a list")
    return value


def _count(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise UnifiedReportPersistenceError(
            f"{field_name} must be a non-negative integer"
        )
    return value


def _generated_at(value: object) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise UnifiedReportPersistenceError("generated_at must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise UnifiedReportPersistenceError(
            "generated_at must be an ISO timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise UnifiedReportPersistenceError("generated_at must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def persist_unified_opportunity_report(
    report: Mapping[str, Any],
    repository: UnifiedOpportunityRepository,
    *,
    source_ref: str = "unified-opportunity-report.json",
) -> dict[str, Any]:
    """Persist canonical snapshots and append meaningful lifecycle transitions.

    Lifecycle events are created only when listing status, evaluation status,
    workflow status, or ``metadata.lifecycle_reason_code`` changes. Replaying the
    same snapshot is idempotent. The adapter does not recalculate lifecycle state.
    """
    if not isinstance(report, Mapping):
        raise UnifiedReportPersistenceError("unified report must be an object")
    if not isinstance(repository, UnifiedOpportunityRepository):
        raise UnifiedReportPersistenceError(
            "repository must be UnifiedOpportunityRepository"
        )

    schema_version = report.get("schema_version")
    if schema_version not in SUPPORTED_UNIFIED_REPORT_SCHEMA_VERSIONS:
        supported = ", ".join(sorted(SUPPORTED_UNIFIED_REPORT_SCHEMA_VERSIONS))
        raise UnifiedReportPersistenceError(
            f"schema_version must be one of: {supported}"
        )

    generated_at = _generated_at(report.get("generated_at"))
    records = _list(report.get("records"), "records")
    conversion_errors = _list(
        report.get("conversion_errors"),
        "conversion_errors",
    )
    if _count(report.get("record_count"), "record_count") != len(records):
        raise UnifiedReportPersistenceError("record_count does not match records")
    if (
        _count(report.get("conversion_error_count"), "conversion_error_count")
        != len(conversion_errors)
    ):
        raise UnifiedReportPersistenceError(
            "conversion_error_count does not match conversion_errors"
        )

    persisted_ids: list[str] = []
    seen_ids: set[str] = set()
    lifecycle_events_created = 0
    lifecycle_repository = LifecycleEventRepository(repository.session)

    for position, raw_record in enumerate(records):
        if not isinstance(raw_record, Mapping):
            raise UnifiedReportPersistenceError(
                f"records[{position}] must be an object"
            )
        opportunity_id = raw_record.get("opportunity_id")
        if not isinstance(opportunity_id, str) or not opportunity_id.strip():
            raise UnifiedReportPersistenceError(
                f"records[{position}].opportunity_id must be a non-empty string"
            )
        normalized_id = opportunity_id.strip()
        if normalized_id in seen_ids:
            raise UnifiedReportPersistenceError(
                f"duplicate opportunity_id in report: {normalized_id}"
            )
        seen_ids.add(normalized_id)

        previous = lifecycle_repository.snapshot_from_model(
            repository.get(normalized_id)
        )
        record_source_ref = f"{source_ref}#{normalized_id}"
        saved = repository.upsert_record(
            raw_record,
            seen_at=generated_at,
            source_ref=record_source_ref,
        )
        current = lifecycle_repository.snapshot_from_model(saved)
        if current is None:
            raise UnifiedReportPersistenceError(
                f"persisted record has no lifecycle snapshot: {normalized_id}"
            )
        event = lifecycle_repository.record_if_changed(
            opportunity_id=normalized_id,
            previous=previous,
            current=current,
            changed_at=generated_at,
            source_ref=record_source_ref,
        )
        if event is not None and previous != current:
            lifecycle_events_created += 1
        persisted_ids.append(normalized_id)

    return {
        "schema_version": schema_version,
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        "persisted_record_count": len(persisted_ids),
        "persisted_opportunity_ids": persisted_ids,
        "lifecycle_events_created": lifecycle_events_created,
        "conversion_error_count": len(conversion_errors),
        "zero_result": not persisted_ids,
        "scope": {
            "json_reports_remain_official": True,
            "changes_discovery": False,
            "changes_lifecycle_classification": False,
            "changes_scoring": False,
            "changes_top5": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        },
    }
