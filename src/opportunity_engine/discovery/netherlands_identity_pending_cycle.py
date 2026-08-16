"""Cross-run Netherlands identity lifecycle wrapper.

This wrapper keeps the existing Netherlands case-memory cycle intact while
adding one pre-case state: ``IDENTITY_PENDING``. It restores pending signals
from the same NL SQLite database, retries identity resolution, and writes still
unresolved rows back to that database. Resolved rows continue through the
existing ENTITY_SCENT and SIGNAL_FOLLOW_UP_ENGINE_V1 path.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from opportunity_engine.discovery import signal_follow_up_memory as entity_memory
from opportunity_engine.discovery.netherlands_case_memory_adapter import (
    ensure_netherlands_memory_database,
    run_netherlands_case_memory_cycle as _run_existing_cycle,
)
from opportunity_engine.discovery.netherlands_identity_pending_memory import (
    load_identity_pending_signals,
    mark_identity_pending_signals,
    merge_pending_with_current_unresolved,
    persist_identity_pending_signals,
    unresolved_signals_from_resolution,
)
from opportunity_engine.discovery.search_provider import SearchProvider


SCHEMA_VERSION = "netherlands-identity-pending-cycle-1.0"
ENGINE_VERSION = "NETHERLANDS_IDENTITY_PENDING_CYCLE_V1"

ProviderFactory = Callable[[str, str], SearchProvider]


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _metadata(signal: Mapping[str, Any]) -> dict[str, Any]:
    value = signal.get("metadata")
    return dict(value) if isinstance(value, Mapping) else {}


def _signal_id_set(signals: Sequence[Mapping[str, Any]]) -> set[str]:
    return {
        signal_id
        for raw in signals
        if isinstance(raw, Mapping)
        and (signal_id := _compact(raw.get("signal_id")))
    }


def _mark_resolved_from_pending(
    entity_rows: Sequence[Mapping[str, Any]],
    *,
    pending_ids_before: set[str],
) -> list[dict[str, Any]]:
    """Move resolved rows out of the pending lifecycle while keeping audit facts."""
    result: list[dict[str, Any]] = []
    for raw in entity_rows:
        if not isinstance(raw, Mapping):
            continue
        row = deepcopy(dict(raw))
        signal_id = _compact(row.get("signal_id"))
        if signal_id in pending_ids_before:
            metadata = _metadata(row)
            metadata["identity_lifecycle_state"] = "IDENTITY_RESOLVED"
            metadata["identity_resolved_from_pending"] = True
            metadata["identity_pending_memory_history_retained"] = True
            row["metadata"] = metadata
        result.append(row)
    return result


def run_netherlands_case_memory_cycle(
    current_signals: Sequence[Mapping[str, Any]],
    *,
    input_root: str | Path,
    cases_report: Mapping[str, Any] | None = None,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory | None = None,
    observed_at: datetime | None = None,
    max_cases: int | None = None,
    results_per_case: int | None = None,
    config_path: str | Path = "alembic.ini",
) -> dict[str, Any]:
    """Retry durable pending identities before the existing NL Follow-Up path."""
    ensure_netherlands_memory_database(input_root, config_path=config_path)
    loaded_pending, pending_load_errors = load_identity_pending_signals(
        input_root=input_root
    )

    fresh_rows = [
        deepcopy(dict(raw))
        for raw in current_signals
        if isinstance(raw, Mapping)
    ]
    current_ids = _signal_id_set(fresh_rows)
    pending_ids_before = _signal_id_set(loaded_pending)
    retry_input = merge_pending_with_current_unresolved(loaded_pending, fresh_rows)

    kwargs: dict[str, Any] = {
        "input_root": input_root,
        "cases_report": cases_report,
        "environment": environment,
        "provider_factory": provider_factory,
        "observed_at": observed_at,
        "config_path": config_path,
    }
    if max_cases is not None:
        kwargs["max_cases"] = max_cases
    if results_per_case is not None:
        kwargs["results_per_case"] = results_per_case

    cycle = _run_existing_cycle(retry_input, **kwargs)
    identity_report = cycle.get("identity_resolution")
    if not isinstance(identity_report, Mapping):
        identity_report = {}

    adapter = cycle.get("adapter")
    raw_entity_rows = (
        adapter.get("entity_signals", []) if isinstance(adapter, Mapping) else []
    )
    entity_rows = _mark_resolved_from_pending(
        [raw for raw in raw_entity_rows if isinstance(raw, Mapping)],
        pending_ids_before=pending_ids_before,
    )
    if isinstance(adapter, dict):
        adapter["entity_signals"] = entity_rows

    resolved_entity_ids = _signal_id_set(entity_rows)
    resolved_from_prior_pending = pending_ids_before & resolved_entity_ids
    resolved_transition_persistence = entity_memory.persist_entity_scent_signals(
        entity_rows,
        input_root=input_root,
    )

    unresolved = unresolved_signals_from_resolution(identity_report)
    pending_rows = mark_identity_pending_signals(
        unresolved,
        resolution_report=identity_report,
        observed_at=observed_at,
    )
    pending_persistence = persist_identity_pending_signals(
        pending_rows,
        input_root=input_root,
    )

    remaining_pending, pending_reload_errors = load_identity_pending_signals(
        input_root=input_root
    )
    remaining_ids = _signal_id_set(remaining_pending)
    new_pending_ids = (remaining_ids - pending_ids_before) & current_ids
    retried_still_pending_ids = pending_ids_before & remaining_ids

    cycle["schema_version"] = "netherlands-case-memory-adapter-1.2"
    cycle["identity_pending_memory"] = {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "loaded_pending_identity_count": len(loaded_pending),
        "retry_input_signal_count": len(retry_input),
        "current_discovery_signal_count": len(fresh_rows),
        "new_pending_identity_count": len(new_pending_ids),
        "retried_still_pending_identity_count": len(retried_still_pending_ids),
        "resolved_from_pending_identity_count": len(resolved_from_prior_pending),
        "remaining_pending_identity_count": len(remaining_pending),
        "remaining_pending_signal_ids": sorted(remaining_ids),
        "pending_load_error_count": len(pending_load_errors),
        "pending_load_errors": pending_load_errors,
        "pending_reload_error_count": len(pending_reload_errors),
        "pending_reload_errors": pending_reload_errors,
        "pending_persistence": pending_persistence,
        "resolved_transition_persistence": resolved_transition_persistence,
        "same_signal_id_transitions_to_entity_scent": True,
        "pending_is_not_entity_scent": True,
        "pending_is_not_follow_up_eligible": True,
        "promotion_to_opportunity_allowed": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    cycle["pending_identity_count"] = len(remaining_pending)
    cycle["resolved_from_pending_identity_count"] = len(resolved_from_prior_pending)
    return cycle
