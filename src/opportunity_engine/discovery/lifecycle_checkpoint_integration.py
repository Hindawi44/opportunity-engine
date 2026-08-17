"""Lifecycle enrichment for the three-market operator checkpoint.

This module reads the already-produced checkpoint, canonical unified reports, and
per-source SQLite persistence artifacts. It never collects, scores, contacts, bids,
buys, reserves, or pays. It only adds truthful lifecycle state and transition
summaries to the operator report.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping, Sequence


WORKFLOW_STATUSES = (
    "EARLY_SIGNAL",
    "CANDIDATE",
    "REQUIRES_VERIFICATION",
    "ACTIVE_OPPORTUNITY",
    "QUALIFIED_OPPORTUNITY",
    "HISTORICAL_MARKET_EVIDENCE",
    "CLOSED",
    "REJECTED",
)
WORKFLOW_RANK = {
    "EARLY_SIGNAL": 1,
    "CANDIDATE": 2,
    "REQUIRES_VERIFICATION": 3,
    "ACTIVE_OPPORTUNITY": 4,
    "QUALIFIED_OPPORTUNITY": 5,
}
TERMINAL_WORKFLOWS = {"HISTORICAL_MARKET_EVIDENCE", "CLOSED", "REJECTED"}


class LifecycleCheckpointIntegrityError(ValueError):
    """Raised when checkpoint lifecycle data violates canonical lifecycle integrity."""


def _read_json(path: Path, *, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleCheckpointIntegrityError(
            f"Invalid lifecycle checkpoint artifact: {path}: {exc}"
        ) from exc


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def _artifact_dir(spec: Mapping[str, Any], root: Path) -> Path:
    return root / _compact(spec.get("artifact_dir"))


def _metadata_reason(record: Mapping[str, Any]) -> str | None:
    metadata = record.get("metadata")
    if not isinstance(metadata, Mapping):
        return None
    value = _compact(metadata.get("lifecycle_reason_code"))
    return value or None


def _canonical_lifecycle_fields(
    record: Mapping[str, Any], *, opportunity_id: str
) -> dict[str, Any]:
    lifecycle = {
        "workflow_status": _compact(record.get("workflow_status")).upper(),
        "evaluation_status": _compact(record.get("evaluation_status")).upper(),
        "lifecycle_reason_code": _metadata_reason(record),
    }
    missing = [key for key, value in lifecycle.items() if not value]
    if missing:
        raise LifecycleCheckpointIntegrityError(
            "incomplete canonical lifecycle truth for "
            f"{opportunity_id}: {', '.join(missing)}"
        )
    return lifecycle


def _canonical_lifecycle_map(
    manifest: Mapping[str, Any], root: Path
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for spec in manifest.get("sources") or []:
        if not isinstance(spec, Mapping):
            continue
        path = _artifact_dir(spec, root) / _compact(
            spec.get("unified_report_file") or "unified-opportunity-report.json"
        )
        payload = _read_json(path, default={}) or {}
        records = payload.get("records") if isinstance(payload, Mapping) else []
        if not isinstance(records, list):
            continue
        for raw in records:
            if not isinstance(raw, Mapping):
                continue
            opportunity_id = _compact(raw.get("opportunity_id"))
            if not opportunity_id:
                continue
            lifecycle = _canonical_lifecycle_fields(
                raw,
                opportunity_id=opportunity_id,
            )
            existing = result.get(opportunity_id)
            if existing is not None and existing != lifecycle:
                raise LifecycleCheckpointIntegrityError(
                    f"conflicting canonical lifecycle truth for {opportunity_id}"
                )
            result[opportunity_id] = lifecycle
    return result


def _enrich_opportunities(
    report: dict[str, Any], canonical: Mapping[str, Mapping[str, Any]]
) -> None:
    records = report.get("deduplicated_opportunities") or []
    for record in records:
        if not isinstance(record, dict):
            continue
        identity = _compact(record.get("opportunity_identity"))
        if not identity:
            raise LifecycleCheckpointIntegrityError(
                "checkpoint opportunity is missing opportunity_identity"
            )
        lifecycle = canonical.get(identity)
        if lifecycle is None:
            raise LifecycleCheckpointIntegrityError(
                f"missing canonical lifecycle truth for {identity}"
            )
        record.update(dict(lifecycle))


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _event_rows(database_path: Path, created_count: int) -> tuple[int, list[dict[str, Any]]]:
    if created_count < 0:
        raise LifecycleCheckpointIntegrityError(
            "lifecycle_events_created must be a non-negative integer"
        )
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        if not _table_exists(connection, "lifecycle_events"):
            raise LifecycleCheckpointIntegrityError(
                f"Lifecycle persistence table missing: {database_path}"
            )
        stored_count = int(
            connection.execute("SELECT COUNT(*) FROM lifecycle_events").fetchone()[0]
        )
        if created_count == 0:
            return stored_count, []
        rows = connection.execute(
            """
            SELECT opportunity_id,
                   from_listing_status, to_listing_status,
                   from_evaluation_status, to_evaluation_status,
                   from_workflow_status, to_workflow_status,
                   from_reason_code, to_reason_code,
                   source_ref, changed_at
            FROM lifecycle_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (created_count,),
        ).fetchall()
        return stored_count, [dict(row) for row in reversed(rows)]
    finally:
        connection.close()


def _restored_paths(restore_status: Mapping[str, Any] | None) -> set[str]:
    if not isinstance(restore_status, Mapping):
        return set()
    paths: set[str] = set()
    for item in restore_status.get("restored_databases") or []:
        if isinstance(item, Mapping):
            value = _compact(item.get("relative_path"))
        else:
            value = _compact(item)
        if value:
            paths.add(value)
    return paths


def _source_persistence(
    spec: Mapping[str, Any],
    root: Path,
    restored_paths: set[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_name = _compact(spec.get("source_name") or spec.get("source"))
    market_code = _compact(spec.get("market_code")).upper()
    directory = _artifact_dir(spec, root)
    summary_path = directory / _compact(
        spec.get("persistence_summary_file") or "unified-persistence-summary.json"
    )
    database_path = directory / _compact(
        spec.get("database_file") or "opportunity_engine.db"
    )
    summary = _read_json(summary_path, default=None)
    relative_database = database_path.relative_to(root).as_posix()

    if not isinstance(summary, Mapping):
        return (
            {
                "market_code": market_code,
                "source_name": source_name,
                "status": "NOT_ENABLED",
                "database_path": None,
                "previous_state_restored": False,
                "lifecycle_events_created_this_run": 0,
                "stored_lifecycle_event_count": 0,
            },
            [],
        )

    if summary.get("status") != "SUCCESS":
        return (
            {
                "market_code": market_code,
                "source_name": source_name,
                "status": "FAILED",
                "database_path": relative_database if database_path.exists() else None,
                "previous_state_restored": relative_database in restored_paths,
                "lifecycle_events_created_this_run": 0,
                "stored_lifecycle_event_count": 0,
            },
            [],
        )

    if not database_path.exists():
        raise LifecycleCheckpointIntegrityError(
            f"{source_name} reports successful persistence but SQLite is missing"
        )
    raw_created = summary.get("lifecycle_events_created", 0)
    if isinstance(raw_created, bool) or not isinstance(raw_created, int):
        raise LifecycleCheckpointIntegrityError(
            f"{source_name} lifecycle_events_created must be an integer"
        )
    stored_count, events = _event_rows(database_path, raw_created)
    for event in events:
        event["market_code"] = market_code
        event["source_name"] = source_name
        event["initial_snapshot"] = all(
            event.get(key) is None
            for key in (
                "from_listing_status",
                "from_evaluation_status",
                "from_workflow_status",
                "from_reason_code",
            )
        )

    return (
        {
            "market_code": market_code,
            "source_name": source_name,
            "status": "SUCCESS",
            "database_path": relative_database,
            "previous_state_restored": relative_database in restored_paths,
            "lifecycle_events_created_this_run": raw_created,
            "stored_lifecycle_event_count": stored_count,
        },
        events,
    )


def _transition_summary(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    transitions = [item for item in events if item.get("initial_snapshot") is not True]
    initial = [item for item in events if item.get("initial_snapshot") is True]
    promoted = 0
    terminal = 0
    for item in transitions:
        previous = _compact(item.get("from_workflow_status")).upper()
        current = _compact(item.get("to_workflow_status")).upper()
        if previous in WORKFLOW_RANK and current in WORKFLOW_RANK:
            promoted += WORKFLOW_RANK[current] > WORKFLOW_RANK[previous]
        if current in TERMINAL_WORKFLOWS and current != previous:
            terminal += 1
    return {
        "events_created_this_run": len(events),
        "initial_snapshots_created_this_run": len(initial),
        "transitions_created_this_run": len(transitions),
        "promoted_count": promoted,
        "closed_historical_or_rejected_count": terminal,
        "current_run_events": list(events),
    }


def _update_human_action(report: dict[str, Any]) -> None:
    action = report.get("next_human_action")
    if not isinstance(action, dict):
        return
    identity = _compact(action.get("opportunity_identity"))
    if not identity:
        return
    target = next(
        (
            item
            for item in report.get("deduplicated_opportunities") or []
            if isinstance(item, Mapping)
            and _compact(item.get("opportunity_identity")) == identity
        ),
        None,
    )
    if not isinstance(target, Mapping):
        return
    workflow = _compact(target.get("workflow_status")).upper()
    action["workflow_status"] = workflow or None
    action["missing_evidence"] = list(target.get("missing_evidence") or [])
    if workflow == "REQUIRES_VERIFICATION":
        action["reason"] = (
            "An active Top 5 candidate requires human verification and evidence "
            "completion before analysis."
        )
    elif workflow == "ACTIVE_OPPORTUNITY":
        action["reason"] = (
            "An active opportunity has complete verification evidence and is ready "
            "for human analysis review."
        )
    elif workflow == "QUALIFIED_OPPORTUNITY":
        action["reason"] = (
            "A qualified opportunity is ready for the final human commercial decision."
        )


def enrich_checkpoint_with_lifecycle(
    report: Mapping[str, Any],
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
    restore_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a checkpoint copy enriched with lifecycle stages and SQLite events."""
    if not isinstance(report, Mapping):
        raise LifecycleCheckpointIntegrityError("checkpoint report must be an object")
    if not isinstance(manifest, Mapping):
        raise LifecycleCheckpointIntegrityError("checkpoint manifest must be an object")

    root_path = Path(root)
    enriched = deepcopy(dict(report))
    canonical = _canonical_lifecycle_map(manifest, root_path)
    _enrich_opportunities(enriched, canonical)

    records = [
        item
        for item in enriched.get("deduplicated_opportunities") or []
        if isinstance(item, Mapping)
    ]
    stage_counter = Counter(_compact(item.get("workflow_status")).upper() for item in records)
    evaluation_counter = Counter(
        _compact(item.get("evaluation_status")).upper() for item in records
    )

    restored = _restored_paths(restore_status)
    source_statuses: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for spec in manifest.get("sources") or []:
        if not isinstance(spec, Mapping):
            continue
        status, source_events = _source_persistence(spec, root_path, restored)
        source_statuses.append(status)
        events.extend(source_events)

    transition_summary = _transition_summary(events)
    enabled = [item for item in source_statuses if item["status"] != "NOT_ENABLED"]
    successful = [item for item in source_statuses if item["status"] == "SUCCESS"]
    restored_successful = [
        item
        for item in successful
        if item.get("previous_state_restored") is True
    ]
    restore_label = _compact((restore_status or {}).get("status")).upper()
    cross_run_continuity = bool(restored_successful)

    enriched["schema_version"] = "multi-market-operator-checkpoint-1.1"
    enriched["lifecycle"] = {
        "stage_counts": {
            status: int(stage_counter.get(status, 0)) for status in WORKFLOW_STATUSES
        },
        "evaluation_status_counts": dict(
            sorted((key, int(value)) for key, value in evaluation_counter.items() if key)
        ),
        "requires_verification_count": int(
            stage_counter.get("REQUIRES_VERIFICATION", 0)
        ),
        "persistence": {
            "enabled_source_count": len(enabled),
            "successful_source_count": len(successful),
            "stored_lifecycle_event_count": sum(
                int(item.get("stored_lifecycle_event_count") or 0)
                for item in successful
            ),
            "previous_state_restore_status": restore_label or "NOT_ATTEMPTED",
            "cross_run_continuity": cross_run_continuity,
            "comparison_scope": (
                "SINCE_PREVIOUS_SUCCESSFUL_CHECKPOINT"
                if cross_run_continuity
                else "CURRENT_RUN_INITIALIZATION"
            ),
            "sources": source_statuses,
        },
        "transitions": transition_summary,
    }
    _update_human_action(enriched)
    return enriched


def render_lifecycle_phone_summary(report: Mapping[str, Any]) -> str:
    """Render the Arabic operator summary with lifecycle state and one action."""
    source_counts = report.get("source_execution_counts") or {}
    status_counts = report.get("status_counts") or {}
    lifecycle = report.get("lifecycle") or {}
    stages = lifecycle.get("stage_counts") or {}
    transitions = lifecycle.get("transitions") or {}
    persistence = lifecycle.get("persistence") or {}
    action = report.get("next_human_action") or {}
    continuity = (
        "مستمر من آخر تشغيل ناجح"
        if persistence.get("cross_run_continuity") is True
        else "تهيئة حالية؛ لا توجد ذاكرة سابقة مستعادة"
    )
    lines = [
        "ملخص الأسواق الثلاثة — مخزون الملابس",
        f"الوقت: {report.get('generated_at')}",
        "التغطية: النرويج NO | السويد SE | ألمانيا DE",
        (
            "المصادر: "
            f"نجاح {source_counts.get('SUCCESS', 0)} | "
            f"صفر صحيح {source_counts.get('VALID_ZERO_RESULT', 0)} | "
            f"فشل {source_counts.get('FAILURE', 0)} | "
            f"محجوب {source_counts.get('BLOCKED', 0)}"
        ),
        (
            "السجلات: "
            f"نشط {status_counts.get('ACTIVE', 0)} | "
            f"قادم {status_counts.get('UPCOMING', 0)} | "
            f"تاريخي {status_counts.get('HISTORICAL', 0)} | "
            f"منتهٍ {status_counts.get('ENDED', 0)} | "
            f"غير محسوم {status_counts.get('UNRESOLVED', 0)}"
        ),
        (
            "دورة الحياة: "
            f"إشارة {stages.get('EARLY_SIGNAL', 0)} | "
            f"مرشح {stages.get('CANDIDATE', 0)} | "
            f"يحتاج تحقق {stages.get('REQUIRES_VERIFICATION', 0)} | "
            f"نشط للتحليل {stages.get('ACTIVE_OPPORTUNITY', 0)} | "
            f"مؤهل {stages.get('QUALIFIED_OPPORTUNITY', 0)}"
        ),
        (
            "انتقالات التشغيل: "
            f"جديدة {transitions.get('transitions_created_this_run', 0)} | "
            f"تقدم {transitions.get('promoted_count', 0)} | "
            f"إغلاق/تاريخي/رفض "
            f"{transitions.get('closed_historical_or_rejected_count', 0)} | "
            f"أحداث أولية {transitions.get('initial_snapshots_created_this_run', 0)}"
        ),
        f"استمرارية SQLite: {continuity}",
        (
            f"Top 5 مؤهل: {report.get('top5_eligible_count', 0)} | "
            f"مؤهل للتحليل: {report.get('analysis_eligible_count', 0)}"
        ),
        f"الإجراء البشري الوحيد: {action.get('action', 'NO_IMMEDIATE_ACTION')}",
        f"السبب: {action.get('reason', '')}",
        "لا شراء، لا مزايدة، لا اتصال، ولا دفع تلقائي.",
    ]
    return "\n".join(lines) + "\n"


def write_lifecycle_checkpoint_artifacts(
    report: Mapping[str, Any],
    report_path: str | Path,
    summary_path: str | Path,
) -> None:
    """Replace checkpoint JSON and phone summary with lifecycle-enriched outputs."""
    Path(report_path).write_text(
        json.dumps(dict(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    Path(summary_path).write_text(
        render_lifecycle_phone_summary(report),
        encoding="utf-8",
    )