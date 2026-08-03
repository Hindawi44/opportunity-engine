"""Complete the Brreg update window with the documented update-id cursor.

The first request is bounded by the requested date window. Subsequent requests
start at the previous batch's last ``oppdateringsid + 1`` as recommended by
Brønnøysundregistrene. The collector remains read-only and never converts a
signal into an opportunity or performs any commercial action.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode, urlparse

from opportunity_engine.discovery.brreg_complete_update_window import (
    _change_paths,
    _page_metadata,
    _update_identity,
)
from opportunity_engine.discovery.direct_official_source_adapters import (
    BRREG_ENTITY_URL,
    BRREG_UPDATES_URL,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_TIMEOUT_SECONDS,
    JsonGetter,
    TextGetter,
    _brreg_signal,
    _brreg_updates,
    _compact,
    _default_json_get,
    _default_text_get,
    _iso_utc,
    _safety_payload,
    _target_spec,
    _update_has_relevant_status_change,
    _write_merged_report,
    probe_german_insolvency_direct_access,
    probe_poit_direct_access,
)


SCHEMA_VERSION = "direct-official-source-adapters-1.2"
DEFAULT_CURSOR_BATCH_SIZE = 2_000
DEFAULT_MAX_CURSOR_RECORDS = 50_000
DEFAULT_MAX_CURSOR_BATCHES = 25
DEFAULT_ENTITY_FETCH_LIMIT = 500


def _cursor_updates_url(
    *,
    observed_at: datetime,
    lookback_days: int,
    batch_size: int,
    cursor_id: int | None,
) -> str:
    params: dict[str, str] = {
        "updatedBefore": observed_at.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "includeChanges": "true",
        "page": "0",
        "size": str(batch_size),
        "sort": "id,ASC",
    }
    if cursor_id is None:
        cutoff = observed_at - timedelta(days=lookback_days)
        params["dato"] = cutoff.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    else:
        params["oppdateringsid"] = str(cursor_id)
    return f"{BRREG_UPDATES_URL}?{urlencode(params)}"


def _is_expected_updates_url(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and (parsed.hostname or "").casefold() == "data.brreg.no"
        and parsed.path == "/enhetsregisteret/api/oppdateringer/enheter"
    )


def _strict_update_ids(updates: Sequence[Mapping[str, Any]]) -> list[int]:
    result: list[int] = []
    for update in updates:
        value = _compact(update.get("oppdateringsid"))
        if not value.isdigit():
            raise RuntimeError("Brreg update omitted a numeric oppdateringsid")
        result.append(int(value))
    if result != sorted(result) or any(
        current <= previous for previous, current in zip(result, result[1:])
    ):
        raise RuntimeError("Brreg updates were not strictly increasing by id")
    return result


def collect_brreg_update_id_cursor_signals(
    *,
    observed_at: datetime,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    batch_size: int = DEFAULT_CURSOR_BATCH_SIZE,
    max_cursor_records: int = DEFAULT_MAX_CURSOR_RECORDS,
    max_cursor_batches: int = DEFAULT_MAX_CURSOR_BATCHES,
    entity_fetch_limit: int = DEFAULT_ENTITY_FETCH_LIMIT,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    json_get: JsonGetter = _default_json_get,
) -> dict[str, Any]:
    """Read a complete bounded update window through ``oppdateringsid`` cursors."""
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    observed_at = observed_at.astimezone(timezone.utc)

    if lookback_days < 1:
        raise ValueError("lookback_days must be at least 1")
    if not 1 <= batch_size <= 10_000:
        raise ValueError("batch_size must be between 1 and 10000")
    if max_cursor_records < 1:
        raise ValueError("max_cursor_records must be positive")
    if max_cursor_batches < 1:
        raise ValueError("max_cursor_batches must be positive")
    if entity_fetch_limit < 1:
        raise ValueError("entity_fetch_limit must be positive")

    headers = {
        "Accept": "application/vnd.brreg.enhetsregisteret.oppdatering.enhet.v1+json",
        "User-Agent": (
            "opportunity-engine/brreg-update-id-cursor "
            "(+https://github.com/Hindawi44/opportunity-engine)"
        ),
    }
    initial_url = _cursor_updates_url(
        observed_at=observed_at,
        lookback_days=lookback_days,
        batch_size=batch_size,
        cursor_id=None,
    )

    updates_by_identity: dict[str, dict[str, Any]] = {}
    cursor_id: int | None = None
    next_cursor_id: int | None = None
    cursor_batch_start_ids: list[int | None] = []
    cursor_batch_counts: list[int] = []
    cursor_batches_fetched = 0
    initial_total_elements: int | None = None
    last_batch_total_elements: int | None = None
    errors: list[str] = []
    update_window_complete = False
    completion_reason = "UNKNOWN"
    last_request_url = initial_url

    for batch_index in range(max_cursor_batches):
        request_url = _cursor_updates_url(
            observed_at=observed_at,
            lookback_days=lookback_days,
            batch_size=batch_size,
            cursor_id=cursor_id,
        )
        last_request_url = request_url
        if not _is_expected_updates_url(request_url):
            errors.append("Generated Brreg cursor URL left the official update endpoint.")
            completion_reason = "INVALID_CURSOR_URL"
            break

        try:
            payload = json_get(request_url, timeout, headers)
            batch_updates = _brreg_updates(payload)
            batch_ids = _strict_update_ids(batch_updates)
        except Exception as exc:
            errors.append(f"batch {batch_index}: {type(exc).__name__}: {exc}")
            completion_reason = (
                "INITIAL_BATCH_FAILED" if batch_index == 0 else "LATER_BATCH_FAILED"
            )
            break

        cursor_batches_fetched += 1
        cursor_batch_start_ids.append(cursor_id)
        cursor_batch_counts.append(len(batch_updates))
        _, _, metadata_total_elements = _page_metadata(payload)
        if batch_index == 0:
            initial_total_elements = metadata_total_elements
        last_batch_total_elements = metadata_total_elements

        if not batch_updates:
            update_window_complete = True
            next_cursor_id = None
            completion_reason = "EMPTY_FINAL_BATCH"
            break

        if cursor_id is not None and batch_ids[0] < cursor_id:
            errors.append(
                "Brreg cursor response regressed below the requested oppdateringsid."
            )
            completion_reason = "CURSOR_REGRESSION"
            break

        remaining_capacity = max_cursor_records - len(updates_by_identity)
        if remaining_capacity <= 0:
            completion_reason = "MAX_CURSOR_RECORDS_REACHED"
            next_cursor_id = cursor_id
            break

        accepted_updates = batch_updates[:remaining_capacity]
        accepted_ids = batch_ids[:remaining_capacity]
        for item in accepted_updates:
            identity = _update_identity(item, len(updates_by_identity))
            updates_by_identity.setdefault(identity, dict(item))

        last_accepted_id = accepted_ids[-1]
        next_cursor_id = last_accepted_id + 1

        if len(accepted_updates) < len(batch_updates):
            completion_reason = "MAX_CURSOR_RECORDS_REACHED"
            break

        if (
            initial_total_elements is not None
            and len(updates_by_identity) >= initial_total_elements
        ):
            update_window_complete = True
            next_cursor_id = None
            completion_reason = "INITIAL_TOTAL_ELEMENTS_REACHED"
            break

        if len(batch_updates) < batch_size:
            update_window_complete = True
            next_cursor_id = None
            completion_reason = "SHORT_FINAL_BATCH"
            break

        if len(updates_by_identity) >= max_cursor_records:
            completion_reason = "MAX_CURSOR_RECORDS_REACHED"
            break

        cursor_id = last_accepted_id + 1
    else:
        completion_reason = "MAX_CURSOR_BATCHES_REACHED"

    updates = list(updates_by_identity.values())
    observed_change_paths = _change_paths(updates)
    update_ids = [
        int(value)
        for value in (_compact(item.get("oppdateringsid")) for item in updates)
        if value.isdigit()
    ]

    if not cursor_batches_fetched and errors:
        return {
            "schema_version": SCHEMA_VERSION,
            "source_key": "BRREG_ENHETSREGISTERET_API",
            "source_name": "Brønnøysundregistrene Enhetsregisteret API",
            "source_country": "NO",
            "generated_at": _iso_utc(observed_at),
            "status": "BLOCKED_DIRECT_ACCESS",
            "access_mode": "DIRECT_OFFICIAL_REST_API",
            "retrieval_mode": "UPDATE_ID_CURSOR",
            "updates_url": initial_url,
            "last_request_url": last_request_url,
            "lookback_days": lookback_days,
            "cursor_batch_size": batch_size,
            "max_cursor_records": max_cursor_records,
            "max_cursor_batches": max_cursor_batches,
            "cursor_batches_fetched": 0,
            "cursor_batch_start_ids": [],
            "cursor_batch_counts": [],
            "initial_total_elements": initial_total_elements,
            "last_batch_total_elements": last_batch_total_elements,
            "retrieval_complete": False,
            "update_window_complete": False,
            "candidate_evaluation_complete": False,
            "next_cursor_available": False,
            "next_cursor_id": None,
            "completion_reason": completion_reason,
            "observed_change_paths": [],
            "retrieved_record_count": 0,
            "candidate_entity_count": 0,
            "entity_fetch_count": 0,
            "accepted_signal_count": 0,
            "rejected_result_count": 0,
            "errors": errors,
            "signals": [],
            **_safety_payload(),
        }

    candidates: dict[str, dict[str, Any]] = {}
    for update in updates:
        orgnr = _compact(update.get("organisasjonsnummer"))
        if orgnr and _update_has_relevant_status_change(update):
            candidates[orgnr] = update

    entity_headers = {
        "Accept": "application/vnd.brreg.enhetsregisteret.enhet.v2+json",
        "User-Agent": headers["User-Agent"],
    }
    signals: dict[str, dict[str, Any]] = {}
    entity_errors: list[str] = []
    rejected = 0
    entity_fetch_count = 0

    for orgnr, update in list(candidates.items())[:entity_fetch_limit]:
        entity_fetch_count += 1
        try:
            entity = json_get(
                BRREG_ENTITY_URL.format(orgnr=orgnr),
                timeout,
                entity_headers,
            )
            if not isinstance(entity, Mapping):
                raise RuntimeError("Brreg entity response must be a JSON object")
        except Exception as exc:
            entity_errors.append(f"{orgnr}: {type(exc).__name__}: {exc}")
            continue

        signal = _brreg_signal(entity, observed_at=observed_at, update=update)
        if signal is None:
            rejected += 1
            continue
        signals[signal.signal_id] = signal.model_dump(mode="json")

    candidate_evaluation_complete = (
        len(candidates) <= entity_fetch_limit and not entity_errors
    )
    retrieval_complete = update_window_complete and candidate_evaluation_complete
    all_errors = [*errors, *entity_errors]

    if retrieval_complete:
        status = "SUCCESS" if signals else "VALID_ZERO"
    else:
        status = "PARTIAL_RETRIEVAL"

    return {
        "schema_version": SCHEMA_VERSION,
        "source_key": "BRREG_ENHETSREGISTERET_API",
        "source_name": "Brønnøysundregistrene Enhetsregisteret API",
        "source_country": "NO",
        "generated_at": _iso_utc(observed_at),
        "status": status,
        "access_mode": "DIRECT_OFFICIAL_REST_API",
        "retrieval_mode": "UPDATE_ID_CURSOR",
        "updates_url": initial_url,
        "last_request_url": last_request_url,
        "lookback_days": lookback_days,
        "cursor_batch_size": batch_size,
        "max_cursor_records": max_cursor_records,
        "max_cursor_batches": max_cursor_batches,
        "cursor_batches_fetched": cursor_batches_fetched,
        "cursor_batch_start_ids": cursor_batch_start_ids,
        "cursor_batch_counts": cursor_batch_counts,
        "initial_total_elements": initial_total_elements,
        "last_batch_total_elements": last_batch_total_elements,
        "retrieval_complete": retrieval_complete,
        "update_window_complete": update_window_complete,
        "candidate_evaluation_complete": candidate_evaluation_complete,
        "next_cursor_available": (not update_window_complete and next_cursor_id is not None),
        "next_cursor_id": next_cursor_id,
        "completion_reason": completion_reason,
        "observed_change_paths": list(observed_change_paths),
        "first_update_id": min(update_ids) if update_ids else None,
        "last_update_id": max(update_ids) if update_ids else None,
        "retrieved_record_count": len(updates),
        "candidate_entity_count": len(candidates),
        "entity_fetch_count": entity_fetch_count,
        "accepted_signal_count": len(signals),
        "rejected_result_count": rejected,
        "errors": all_errors,
        "signals": [signals[key] for key in sorted(signals)],
        **_safety_payload(),
    }


def collect_manifest_cursor_direct_official_signals(
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
    observed_at: datetime | None = None,
    json_get: JsonGetter = _default_json_get,
    text_get: TextGetter = _default_text_get,
) -> dict[str, Any]:
    """Collect all three official sources with cursor semantics for Norway."""
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    reports = [
        collect_brreg_update_id_cursor_signals(observed_at=now, json_get=json_get),
        probe_poit_direct_access(observed_at=now, text_get=text_get),
        probe_german_insolvency_direct_access(observed_at=now, text_get=text_get),
    ]
    root_path = Path(root)
    for report in reports:
        report["schema_version"] = SCHEMA_VERSION
        market_code = _compact(report.get("source_country")).upper()
        target = _target_spec(manifest, market_code)
        if target is None:
            report["status"] = "BLOCKED_DIRECT_ACCESS"
            report.setdefault("errors", []).append(
                "No checkpoint artifact directory exists for this market."
            )
            continue
        artifact_dir = root_path / _compact(target.get("artifact_dir"))
        report_path = artifact_dir / _compact(
            target.get("market_signal_report_file")
            or "market-signal-report.json"
        )
        report["stored_signal_count"] = _write_merged_report(report_path, report)
        report["artifact_path"] = report_path.relative_to(root_path).as_posix()

    status_counts: dict[str, int] = {}
    for report in reports:
        status = _compact(report.get("status")).upper() or "UNKNOWN"
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso_utc(now),
        "retrieval_transport": "DIRECT_OFFICIAL_SOURCE",
        "market_coverage": ["NO", "SE", "DE"],
        "source_count": len(reports),
        "status_counts": status_counts,
        "sources": reports,
        "signal_count": sum(
            int(report.get("accepted_signal_count") or 0)
            for report in reports
        ),
        **_safety_payload(),
    }
