"""Optional live persistence for a completed unified opportunity report.

JSON remains the official report. This module only copies a completed report into
SQLite when explicitly requested by the caller. Persistence failures are surfaced
without deleting or rewriting discovery artifacts.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from .database import (
    DEFAULT_DATABASE_URL,
    create_database_engine,
    create_session_factory,
    session_scope,
    upgrade_database,
)
from .repository import OpportunityRepository
from .unified_report_adapter import persist_unified_opportunity_report
from .unified_repository import UnifiedOpportunityRepository


PIPELINE_NAME = "UNIFIED_DISCOVERY_PERSISTENCE_V1"
SUMMARY_FILENAME = "unified-persistence-summary.json"
ERROR_FILENAME = "unified-persistence-error.json"


class UnifiedPersistenceExecutionError(RuntimeError):
    """Raised after a structured persistence-error artifact has been written."""

    def __init__(self, message: str, *, artifact_path: Path) -> None:
        super().__init__(message)
        self.artifact_path = artifact_path


def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _load_report(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"unified report does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"unified report is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("unified report root must be an object")
    return payload


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("generated_at must be an ISO timestamp")
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _run_id(generated_at: datetime) -> str:
    return f"unified-discovery-{generated_at.strftime('%Y%m%dT%H%M%S%fZ')}"


def _database_backend(database_url: str) -> str:
    value = str(database_url).strip()
    return value.split(":", 1)[0] if ":" in value else "unknown"


def persist_unified_report_file(
    report_path: str | Path,
    *,
    database_url: str = DEFAULT_DATABASE_URL,
    config_path: str | Path = "alembic.ini",
) -> dict[str, Any]:
    """Apply migrations and atomically copy one report into durable storage."""
    source_path = Path(report_path)
    report = _load_report(source_path)
    generated_at = _timestamp(report.get("generated_at"))
    finished_at = datetime.now(timezone.utc)
    if finished_at < generated_at:
        finished_at = generated_at

    upgrade_database(database_url, config_path=config_path)
    engine = create_database_engine(database_url)
    try:
        factory = create_session_factory(engine)
        with session_scope(factory) as session:
            summary = persist_unified_opportunity_report(
                report,
                UnifiedOpportunityRepository(session),
                source_ref=str(source_path),
            )
            run_id = _run_id(generated_at)
            OpportunityRepository(session).record_source_run(
                {
                    "run_id": run_id,
                    "pipeline_name": PIPELINE_NAME,
                    "status": "SUCCESS",
                    "started_at": generated_at,
                    "finished_at": finished_at,
                    "zero_result": summary["zero_result"],
                    "summary": {
                        "schema_version": summary["schema_version"],
                        "generated_at": summary["generated_at"],
                        "persisted_record_count": summary["persisted_record_count"],
                        "persisted_opportunity_ids": summary[
                            "persisted_opportunity_ids"
                        ],
                        "conversion_error_count": summary[
                            "conversion_error_count"
                        ],
                        "report_path": str(source_path),
                        "json_reports_remain_official": True,
                    },
                }
            )
    finally:
        engine.dispose()

    return {
        **summary,
        "run_id": run_id,
        "pipeline_name": PIPELINE_NAME,
        "database_backend": _database_backend(database_url),
        "report_path": str(source_path),
        "json_reports_remain_official": True,
    }


def persist_unified_report_with_artifacts(
    report_path: str | Path,
    output_dir: str | Path,
    *,
    database_url: str = DEFAULT_DATABASE_URL,
    config_path: str | Path = "alembic.ini",
) -> tuple[dict[str, Any], Path]:
    """Persist a report and write either a success or structured error artifact."""
    source_path = Path(report_path)
    destination = Path(output_dir)
    try:
        summary = persist_unified_report_file(
            source_path,
            database_url=database_url,
            config_path=config_path,
        )
    except Exception as exc:
        error_path = destination / ERROR_FILENAME
        _write_json(
            error_path,
            {
                "status": "FAILED",
                "pipeline_name": PIPELINE_NAME,
                "report_path": str(source_path),
                "database_backend": _database_backend(database_url),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "json_reports_remain_official": True,
                "report_deleted": False,
            },
        )
        raise UnifiedPersistenceExecutionError(
            f"unified SQLite persistence failed: {exc}",
            artifact_path=error_path,
        ) from exc

    summary_path = destination / SUMMARY_FILENAME
    _write_json(summary_path, {"status": "SUCCESS", **summary})
    return summary, summary_path
