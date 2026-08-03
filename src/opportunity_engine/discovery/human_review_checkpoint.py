"""Reconcile persisted human review state into the operator checkpoint."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping


_CHECKPOINT_STATUSES = ("ACTIVE", "ENDED", "HISTORICAL", "UNRESOLVED", "UPCOMING")
_TERMINAL_LISTING = {"ENDED", "SOLD", "UNAVAILABLE"}


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def _checkpoint_listing(value: object, workflow: object) -> str:
    listing = _compact(value).upper()
    lifecycle = _compact(workflow).upper()
    if lifecycle == "HISTORICAL_MARKET_EVIDENCE":
        return "HISTORICAL"
    if listing in _TERMINAL_LISTING:
        return "ENDED"
    if listing == "ACTIVE":
        return "ACTIVE"
    if listing == "UPCOMING":
        return "UPCOMING"
    return "UNRESOLVED"


def _missing(record: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for raw in record.get("missing_information") or []:
        if isinstance(raw, Mapping):
            text = _compact(raw.get("field_name"))
        else:
            text = _compact(raw)
        if text:
            values.append(text)
    return sorted(set(values))


def _reviewed_records(manifest: Mapping[str, Any], root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for spec in manifest.get("sources") or []:
        if not isinstance(spec, Mapping):
            continue
        directory = root / _compact(spec.get("artifact_dir"))
        database = directory / _compact(spec.get("database_file") or "opportunity_engine.db")
        if not database.exists():
            continue
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        try:
            table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='human_review_outcomes'"
            ).fetchone()
            if table is None:
                continue
            rows = connection.execute(
                """
                SELECT opportunity_id, record_json
                FROM unified_opportunities
                WHERE opportunity_id IN (
                    SELECT DISTINCT opportunity_id FROM human_review_outcomes
                )
                """
            ).fetchall()
        finally:
            connection.close()
        for row in rows:
            raw = row["record_json"]
            if isinstance(raw, str):
                try:
                    record = json.loads(raw)
                except json.JSONDecodeError:
                    continue
            elif isinstance(raw, Mapping):
                record = dict(raw)
            else:
                continue
            metadata = record.get("metadata")
            if not isinstance(metadata, Mapping) or not isinstance(
                metadata.get("human_review"), Mapping
            ):
                continue
            result[str(row["opportunity_id"])] = record
    return result


def _apply_reviewed_records(
    report: dict[str, Any], reviewed: Mapping[str, Mapping[str, Any]]
) -> None:
    for item in report.get("deduplicated_opportunities") or []:
        if not isinstance(item, dict):
            continue
        identity = _compact(item.get("opportunity_identity"))
        raw = reviewed.get(identity)
        if not isinstance(raw, Mapping):
            continue
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), Mapping) else {}
        item.update(
            {
                "listing_status": _checkpoint_listing(
                    raw.get("listing_status"), raw.get("workflow_status")
                ),
                "evaluation_status": _compact(raw.get("evaluation_status")).upper(),
                "workflow_status": _compact(raw.get("workflow_status")).upper(),
                "lifecycle_reason_code": _compact(
                    metadata.get("lifecycle_reason_code")
                )
                or None,
                "verified": raw.get("verified") is True,
                "analysis_eligible": raw.get("analysis_eligible") is True,
                "top5_eligible": raw.get("top5_eligible") is True
                and _checkpoint_listing(
                    raw.get("listing_status"), raw.get("workflow_status")
                )
                == "ACTIVE",
                "missing_evidence": _missing(raw),
                "analysis_tasks": list(metadata.get("analysis_tasks") or []),
                "human_review": dict(metadata.get("human_review") or {}),
            }
        )


def _recalculate(report: dict[str, Any]) -> None:
    records = [
        item
        for item in report.get("deduplicated_opportunities") or []
        if isinstance(item, Mapping)
    ]
    status = Counter(_compact(item.get("listing_status")).upper() for item in records)
    report["status_counts"] = {
        key: int(status.get(key, 0)) for key in _CHECKPOINT_STATUSES
    }
    report["top5_eligible_count"] = sum(
        item.get("top5_eligible") is True and item.get("listing_status") == "ACTIVE"
        for item in records
    )
    report["analysis_eligible_count"] = sum(
        item.get("analysis_eligible") is True and item.get("listing_status") == "ACTIVE"
        for item in records
    )

    for market in report.get("markets") or []:
        if not isinstance(market, dict):
            continue
        code = _compact(market.get("market_code")).upper()
        scoped = [item for item in records if item.get("market_code") == code]
        market["active_count"] = sum(
            item.get("listing_status") == "ACTIVE" for item in scoped
        )
        market["top5_eligible_count"] = sum(
            item.get("top5_eligible") is True
            and item.get("listing_status") == "ACTIVE"
            for item in scoped
        )
        market["deduplicated_record_count"] = len(scoped)

    lifecycle = report.get("lifecycle")
    if isinstance(lifecycle, dict):
        stage = Counter(_compact(item.get("workflow_status")).upper() for item in records)
        evaluation = Counter(
            _compact(item.get("evaluation_status")).upper() for item in records
        )
        existing = lifecycle.get("stage_counts") or {}
        lifecycle["stage_counts"] = {
            key: int(stage.get(key, 0)) for key in existing
        }
        lifecycle["evaluation_status_counts"] = dict(
            sorted((key, int(value)) for key, value in evaluation.items() if key)
        )
        lifecycle["requires_verification_count"] = int(
            stage.get("REQUIRES_VERIFICATION", 0)
        )


def _select_action(report: dict[str, Any]) -> None:
    candidates = [
        item
        for item in report.get("deduplicated_opportunities") or []
        if isinstance(item, Mapping)
        and item.get("listing_status") == "ACTIVE"
        and item.get("top5_eligible") is True
    ]
    if not candidates:
        report["next_human_action"] = {
            "action": "NO_ACTION",
            "opportunity_identity": None,
            "reason": "No active Top 5 opportunity is currently available.",
        }
        return

    priority = {
        "QUALIFIED_OPPORTUNITY": 0,
        "ACTIVE_OPPORTUNITY": 1,
        "REQUIRES_VERIFICATION": 2,
    }
    target = min(
        enumerate(candidates),
        key=lambda pair: (
            priority.get(_compact(pair[1].get("workflow_status")).upper(), 3),
            pair[0],
        ),
    )[1]
    workflow = _compact(target.get("workflow_status")).upper()
    if workflow == "QUALIFIED_OPPORTUNITY":
        reason = "A qualified opportunity is ready for the final human commercial decision."
    elif workflow == "ACTIVE_OPPORTUNITY":
        reason = "A verified active opportunity is ready for human analysis review."
    else:
        reason = (
            "An active Top 5 candidate requires human verification and evidence "
            "completion before analysis."
        )
    report["next_human_action"] = {
        "action": "REVIEW_ONE_OPPORTUNITY",
        "opportunity_identity": target.get("opportunity_identity"),
        "reason": reason,
        "workflow_status": workflow,
        "missing_evidence": list(target.get("missing_evidence") or []),
        "analysis_tasks": list(target.get("analysis_tasks") or []),
    }


def reconcile_checkpoint_human_reviews(
    report: Mapping[str, Any],
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
) -> dict[str, Any]:
    """Return a checkpoint copy aligned with persisted human decisions."""
    if not isinstance(report, Mapping) or not isinstance(manifest, Mapping):
        raise ValueError("report and manifest must be objects")
    reconciled = deepcopy(dict(report))
    reviewed = _reviewed_records(manifest, Path(root))
    _apply_reviewed_records(reconciled, reviewed)
    _recalculate(reconciled)
    _select_action(reconciled)
    reconciled["human_review_outcome_count"] = len(reviewed)
    return reconciled
