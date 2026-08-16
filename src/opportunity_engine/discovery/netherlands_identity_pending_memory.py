"""Durable pre-identity memory for Netherlands market signals.

Dutch discovery can surface a real clothing insolvency before the legal company
name is visible. Those signals must not become ENTITY_SCENT cases yet, but they
also must not disappear just because the search result is absent on the next
run. This module stores the same MarketSignalRecord in the existing Netherlands
SQLite database with an ``IDENTITY_PENDING`` lifecycle marker.

The same ``signal_id`` is retained. Once identity resolution later succeeds, the
normal Netherlands case-memory adapter upserts that same signal as ENTITY_SCENT,
so there is no parallel case table or second memory architecture.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from opportunity_engine.discovery.netherlands_market_discovery import FEED_FAMILY
from opportunity_engine.persistence import (
    MarketSignalRepository,
    create_database_engine,
    create_session_factory,
    session_scope,
)


SCHEMA_VERSION = "netherlands-identity-pending-memory-1.0"
ENGINE_VERSION = "NETHERLANDS_IDENTITY_PENDING_MEMORY_V1"
MARKET_CODE = "NL"
IDENTITY_PENDING = "IDENTITY_PENDING"
NETHERLANDS_MEMORY_RELATIVE_PATH = Path("nl-market/opportunity_engine.db")

_LIFECYCLE_KEYS = (
    "identity_lifecycle_state",
    "identity_pending_memory",
    "identity_pending_since",
    "identity_resolution_attempt_count",
    "identity_last_attempt_at",
    "identity_last_resolution_status",
    "identity_original_latest_observed_at",
)
_ENTITY_MEMORY_KEYS = (
    "entity_scent_classification",
    "entity_scent_quality_gate",
    "entity_key",
    "entity_label",
    "entity_shape",
    "entity_cluster_score",
    "entity_evidence_count",
    "entity_independent_source_count",
)


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _utc(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _metadata(signal: Mapping[str, Any]) -> dict[str, Any]:
    value = signal.get("metadata")
    return dict(value) if isinstance(value, Mapping) else {}


def _database_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _is_netherlands_discovery_signal(signal: Mapping[str, Any]) -> bool:
    metadata = _metadata(signal)
    return (
        _compact(signal.get("source_country")).upper() == MARKET_CODE
        and _compact(metadata.get("feed_family")) == FEED_FAMILY
        and bool(_compact(signal.get("signal_id")))
    )


def is_identity_pending_signal(signal: Mapping[str, Any]) -> bool:
    metadata = _metadata(signal)
    return (
        _is_netherlands_discovery_signal(signal)
        and _compact(metadata.get("identity_lifecycle_state")).upper()
        == IDENTITY_PENDING
        and not _compact(signal.get("company_name") or signal.get("seller_name"))
    )


def merge_pending_with_current_unresolved(
    persisted_pending: Sequence[Mapping[str, Any]],
    current_unresolved: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build one retry queue, preserving pending lifecycle history by signal id.

    Persisted pending rows are ordered first so an old scent cannot be starved by
    newly discovered unnamed signals. If the same signal is rediscovered, the
    fresh market payload wins while its pending lifecycle counters are retained.
    """
    persisted_by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for raw in persisted_pending:
        if not isinstance(raw, Mapping) or not is_identity_pending_signal(raw):
            continue
        signal_id = _compact(raw.get("signal_id"))
        if signal_id and signal_id not in persisted_by_id:
            persisted_by_id[signal_id] = deepcopy(dict(raw))
            order.append(signal_id)

    current_by_id: dict[str, dict[str, Any]] = {}
    for raw in current_unresolved:
        if not isinstance(raw, Mapping) or not _is_netherlands_discovery_signal(raw):
            continue
        signal_id = _compact(raw.get("signal_id"))
        if not signal_id:
            continue
        fresh = deepcopy(dict(raw))
        previous = persisted_by_id.get(signal_id)
        if previous is not None:
            previous_metadata = _metadata(previous)
            fresh_metadata = _metadata(fresh)
            for key in _LIFECYCLE_KEYS:
                if key in previous_metadata and key not in fresh_metadata:
                    fresh_metadata[key] = previous_metadata[key]
            fresh["metadata"] = fresh_metadata
            first_seen = _compact(previous.get("first_observed_at"))
            if first_seen:
                fresh["first_observed_at"] = first_seen
        current_by_id[signal_id] = fresh
        if signal_id not in persisted_by_id:
            order.append(signal_id)

    merged: list[dict[str, Any]] = []
    for signal_id in order:
        merged.append(current_by_id.get(signal_id) or persisted_by_id[signal_id])
    return merged


def _resolution_by_signal_id(
    resolution_report: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    rows = resolution_report.get("resolutions")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return result
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        signal_id = _compact(raw.get("signal_id"))
        if signal_id:
            result[signal_id] = dict(raw)
    return result


def unresolved_signals_from_resolution(
    resolution_report: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return resolver outputs that still have no approved identity."""
    rows = resolution_report.get("enriched_signals")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return []
    unresolved: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        metadata = _metadata(raw)
        status = _compact(metadata.get("entity_identity_resolution_status")).upper()
        company = _compact(raw.get("company_name") or raw.get("seller_name"))
        if company or status.startswith("RESOLVED_"):
            continue
        if _is_netherlands_discovery_signal(raw):
            unresolved.append(deepcopy(dict(raw)))
    return unresolved


def mark_identity_pending_signals(
    signals: Sequence[Mapping[str, Any]],
    *,
    resolution_report: Mapping[str, Any],
    observed_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Mark unresolved signals for durable retry without making them cases."""
    now = _utc(observed_at)
    report_status = _compact(resolution_report.get("status")).upper()
    resolution_map = _resolution_by_signal_id(resolution_report)
    pending: list[dict[str, Any]] = []

    for raw in signals:
        if not isinstance(raw, Mapping) or not _is_netherlands_discovery_signal(raw):
            continue
        payload = deepcopy(dict(raw))
        metadata = _metadata(payload)
        signal_id = _compact(payload.get("signal_id"))
        resolution = resolution_map.get(signal_id)
        if resolution is not None:
            resolution_status = _compact(resolution.get("status")) or "UNRESOLVED"
        elif report_status.startswith("SKIPPED_NO_API_KEY"):
            resolution_status = report_status
        else:
            resolution_status = "NOT_ATTEMPTED_BOUNDED_BUDGET"

        prior_attempts = int(metadata.get("identity_resolution_attempt_count") or 0)
        attempt_performed = resolution is not None
        if resolution_status == "SKIPPED_ALREADY_IDENTIFIED":
            attempt_performed = False

        original_latest = (
            _compact(metadata.get("identity_original_latest_observed_at"))
            or _compact(payload.get("latest_observed_at"))
            or _compact(payload.get("observed_at"))
            or now.isoformat()
        )
        pending_since = (
            _compact(metadata.get("identity_pending_since"))
            or _compact(payload.get("first_observed_at"))
            or original_latest
        )

        for key in _ENTITY_MEMORY_KEYS:
            metadata.pop(key, None)
        metadata.update(
            {
                "identity_lifecycle_state": IDENTITY_PENDING,
                "identity_pending_memory": ENGINE_VERSION,
                "identity_pending_since": pending_since,
                "identity_resolution_attempt_count": prior_attempts
                + int(attempt_performed),
                "identity_last_resolution_status": resolution_status,
                "identity_original_latest_observed_at": original_latest,
                "signal_only": True,
                "not_an_opportunity": True,
                "identity_required_before_memory": True,
                "source_page_verification_required": True,
                "promotion_to_opportunity_allowed": False,
                "top5_eligible": False,
                "analysis_eligible": False,
                "automatic_contact": False,
                "automatic_bid": False,
                "automatic_reservation": False,
                "automatic_purchase": False,
                "automatic_payment": False,
            }
        )
        if attempt_performed:
            metadata["identity_last_attempt_at"] = now.isoformat()

        payload["metadata"] = metadata
        payload["company_name"] = None
        payload["seller_name"] = None
        # Do not move market recency forward merely because identity resolution
        # was retried. Retry time lives only in identity_last_attempt_at.
        payload["status"] = "WATCH"
        pending.append(payload)
    return pending


def persist_identity_pending_signals(
    signals: Sequence[Mapping[str, Any]],
    *,
    input_root: str | Path,
) -> dict[str, Any]:
    """Upsert pending rows into the existing NL market-signal database."""
    stable: dict[str, dict[str, Any]] = {}
    for raw in signals:
        if isinstance(raw, Mapping) and is_identity_pending_signal(raw):
            signal_id = _compact(raw.get("signal_id"))
            if signal_id:
                stable[signal_id] = deepcopy(dict(raw))

    path = Path(input_root) / NETHERLANDS_MEMORY_RELATIVE_PATH
    saved = changed = 0
    errors: list[str] = []
    if stable and not path.exists():
        errors.append(f"NL: memory database missing: {path.as_posix()}")
    elif stable:
        engine = create_database_engine(_database_url(path))
        try:
            factory = create_session_factory(engine)
            with session_scope(factory) as session:
                repository = MarketSignalRepository(session)
                for signal_id in sorted(stable):
                    result = repository.upsert_signal(stable[signal_id])
                    saved += 1
                    changed += int(bool(result.get("created") or result.get("changed")))
        except Exception as exc:  # pending continuity must not block the bulletin
            errors.append(f"NL: {type(exc).__name__}: {_compact(exc)[:300]}")
        finally:
            engine.dispose()

    return {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "backend": "EXISTING_NL_SQLITE_MARKET_SIGNALS",
        "input_pending_signal_count": len(stable),
        "persisted_pending_signal_count": saved,
        "new_or_changed_pending_signal_count": changed,
        "database": path.as_posix(),
        "errors": errors,
    }


def load_identity_pending_signals(
    *, input_root: str | Path
) -> tuple[list[dict[str, Any]], list[str]]:
    """Load unresolved NL identities from the same restored SQLite state."""
    path = Path(input_root) / NETHERLANDS_MEMORY_RELATIVE_PATH
    if not path.exists():
        return [], []

    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    engine = create_database_engine(_database_url(path))
    try:
        factory = create_session_factory(engine)
        with session_scope(factory) as session:
            repository = MarketSignalRepository(session)
            for model in repository.list_current():
                payload = model.payload_json
                if isinstance(payload, Mapping) and is_identity_pending_signal(payload):
                    rows.append(deepcopy(dict(payload)))
    except Exception as exc:
        errors.append(f"NL: {type(exc).__name__}: {_compact(exc)[:300]}")
    finally:
        engine.dispose()

    rows.sort(
        key=lambda item: (
            int(_metadata(item).get("identity_resolution_attempt_count") or 0),
            _compact(_metadata(item).get("identity_last_attempt_at")),
            _compact(item.get("signal_id")),
        )
    )
    return rows, errors
