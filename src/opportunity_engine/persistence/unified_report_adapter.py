"""Persist unified-opportunity-report.json through the canonical repository."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from .repository import PersistenceError
from .unified_repository import UnifiedOpportunityRepository


UNIFIED_REPORT_SCHEMA_VERSION = "1.0"


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
    """Persist all canonical records from one validated report envelope.

    The adapter copies canonical values and the original record JSON. It does not
    estimate missing values, recalculate lifecycle states, or modify discovery
    reports.
    """
    if not isinstance(report, Mapping):
        raise UnifiedReportPersistenceError("unified report must be an object")
    if not isinstance(repository, UnifiedOpportunityRepository):
        raise UnifiedReportPersistenceError(
            "repository must be UnifiedOpportunityRepository"
        )

    schema_version = report.get("schema_version")
    if schema_version != UNIFIED_REPORT_SCHEMA_VERSION:
        raise UnifiedReportPersistenceError(
            f"schema_version must be {UNIFIED_REPORT_SCHEMA_VERSION}"
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
        repository.upsert_record(
            raw_record,
            seen_at=generated_at,
            source_ref=f"{source_ref}#{normalized_id}",
        )
        persisted_ids.append(normalized_id)

    return {
        "schema_version": schema_version,
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        "persisted_record_count": len(persisted_ids),
        "persisted_opportunity_ids": persisted_ids,
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
