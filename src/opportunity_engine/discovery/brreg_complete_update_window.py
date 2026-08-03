"""Complete the bounded Brreg update window before declaring a valid zero.

This module keeps the direct official-source architecture introduced in v1.0,
but replaces the Norway page-zero read with bounded, truthful pagination across
the requested update window. Sweden and Germany retain their existing direct
portal probes and no-bypass behavior.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode, urlparse

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


SCHEMA_VERSION = "direct-official-source-adapters-1.1"
DEFAULT_PAGE_SIZE = 500
DEFAULT_MAX_UPDATE_RECORDS = 10_000
DEFAULT_MAX_PAGES = 20
DEFAULT_ENTITY_FETCH_LIMIT = 500


def _page_metadata(payload: object) -> tuple[int | None, int | None, int | None]:
    if not isinstance(payload, Mapping):
        return None, None, None
    page = payload.get("page")
    if not isinstance(page, Mapping):
        return None, None, None

    def _integer(key: str) -> int | None:
        value = page.get(key)
        if isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    return _integer("number"), _integer("totalPages"), _integer("totalElements")


def _change_paths(updates: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    paths: set[str] = set()
    for update in updates:
        changes = update.get("endringer")
        if not isinstance(changes, Sequence) or isinstance(changes, (str, bytes)):
            continue
        for change in changes:
            if not isinstance(change, Mapping):
                continue
            path = _compact(change.get("path"))
            if path:
                paths.add(path)
    return tuple(sorted(paths))


def _update_identity(update: Mapping[str, Any], fallback_index: int) -> str:
    update_id = _compact(update.get("oppdateringsid"))
    if update_id:
        return f"id:{update_id}"
    return "fallback:{orgnr}:{date}:{index}".format(
        orgnr=_compact(update.get("organisasjonsnummer")),
        date=_compact(update.get("dato")),
        index=fallback_index,
    )


def _official_updates_url(
    *,
    observed_at: datetime,
    lookback_days: int,
    page: int,
    page_size: int,
) -> str:
    cutoff = observed_at - timedelta(days=lookback_days)
    params = urlencode(
        {
            "dato": cutoff.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "updatedBefore": observed_at.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "includeChanges": "true",
            "page": str(page),
            "size": str(page_size),
            "sort": "id,ASC",
        }
    )
    return f"{BRREG_UPDATES_URL}?{params}"


def _is_expected_brreg_updates_url(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and (parsed.hostname or "").casefold() == "data.brreg.no"
        and parsed.path == "/enhetsregisteret/api/oppdateringer/enheter"
    )


def collect_brreg_complete_window_signals(
    *,
    observed_at: datetime,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_update_records: int = DEFAULT_MAX_UPDATE_RECORDS,
    max_pages: int = DEFAULT_MAX_PAGES,
    entity_fetch_limit: int = DEFAULT_ENTITY_FETCH_LIMIT,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    json_get: JsonGetter = _default_json_get,
) -> dict[str, Any]:
    """Read the complete bounded Brreg update window before returning VALID_ZERO."""
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    observed_at = observed_at.astimezone(timezone.utc)

    if lookback_days < 1:
        raise ValueError("lookback_days must be at least 1")
    if not 1 <= page_size <= 10_000:
        raise ValueError("page_size must be between 1 and 10000")
    if not 1 <= max_update_records <= 10_000:
        raise ValueError("max_update_records must be between 1 and 10000")
    if max_pages < 1:
        raise ValueError("max_pages must be positive")
    if entity_fetch_limit < 1:
        raise ValueError("entity_fetch_limit must be positive")

    bounded_page_limit = min(max_pages, math.ceil(max_update_records / page_size))
    headers = {
        "Accept": "application/vnd.brreg.enhetsregisteret.oppdatering.enhet.v1+json",
        "User-Agent": (
            "opportunity-engine/brreg-complete-update-window "
            "(+https://github.com/Hindawi44/opportunity-engine)"
        ),
    }
    initial_url = _official_updates_url(
        observed_at=observed_at,
        lookback_days=lookback_days,
        page=0,
        page_size=page_size,
    )

    updates_by_identity: dict[str, dict[str, Any]] = {}
    pages_fetched = 0
    total_elements: int | None = None
    page_errors: list[str] = []
    update_window_complete = False
    next_page_available = False
    completion_reason = "UNKNOWN"

    for page_number in range(bounded_page_limit):
        page_url = _official_updates_url(
            observed_at=observed_at,
            lookback_days=lookback_days,
            page=page_number,
            page_size=page_size,
        )
        if not _is_expected_brreg_updates_url(page_url):
            page_errors.append("Generated Brreg page URL left the official update endpoint.")
            completion_reason = "INVALID_PAGE_URL"
            break
        try:
            payload = json_get(page_url, timeout, headers)
            page_updates = _brreg_updates(payload)
        except Exception as exc:
            page_errors.append(f"page {page_number}: {type(exc).__name__}: {exc}")
            completion_reason = (
                "INITIAL_PAGE_FAILED" if page_number == 0 else "LATER_PAGE_FAILED"
            )
            break

        pages_fetched += 1
        metadata_number, metadata_total_pages, metadata_total_elements = (
            _page_metadata(payload)
        )
        if metadata_total_elements is not None:
            total_elements = max(total_elements or 0, metadata_total_elements)

        for item in page_updates:
            identity = _update_identity(item, len(updates_by_identity))
            updates_by_identity.setdefault(identity, item)
            if len(updates_by_identity) >= max_update_records:
                break

        metadata_has_more = (
            metadata_total_pages is not None
            and (metadata_number if metadata_number is not None else page_number) + 1
            < metadata_total_pages
        )
        inferred_has_more = len(page_updates) >= page_size
        next_page_available = metadata_has_more or (
            metadata_total_pages is None and inferred_has_more
        )

        if len(updates_by_identity) >= max_update_records:
            if next_page_available or (
                total_elements is not None
                and total_elements > len(updates_by_identity)
            ):
                completion_reason = "MAX_UPDATE_RECORDS_REACHED"
                update_window_complete = False
            else:
                completion_reason = "EXACT_BOUNDARY_COMPLETE"
                update_window_complete = True
                next_page_available = False
            break

        if metadata_total_pages is not None:
            current_page = (
                metadata_number if metadata_number is not None else page_number
            )
            if current_page + 1 >= metadata_total_pages:
                completion_reason = "PAGE_METADATA_COMPLETE"
                update_window_complete = True
                next_page_available = False
                break
            continue

        if len(page_updates) < page_size:
            completion_reason = "SHORT_FINAL_PAGE"
            update_window_complete = True
            next_page_available = False
            break
    else:
        completion_reason = "MAX_PAGES_REACHED"
        update_window_complete = False
        next_page_available = True

    updates = list(updates_by_identity.values())
    observed_change_paths = _change_paths(updates)
    update_ids = [
        int(value)
        for value in (_compact(item.get("oppdateringsid")) for item in updates)
        if value.isdigit()
    ]

    if not pages_fetched and page_errors:
        return {
            "schema_version": SCHEMA_VERSION,
            "source_key": "BRREG_ENHETSREGISTERET_API",
            "source_name": "Brønnøysundregistrene Enhetsregisteret API",
            "source_country": "NO",
            "generated_at": _iso_utc(observed_at),
            "status": "BLOCKED_DIRECT_ACCESS",
            "access_mode": "DIRECT_OFFICIAL_REST_API",
            "updates_url": initial_url,
            "lookback_days": lookback_days,
            "page_size": page_size,
            "max_update_records": max_update_records,
            "max_pages": bounded_page_limit,
            "pages_fetched": 0,
            "total_elements": total_elements,
            "retrieval_complete": False,
            "update_window_complete": False,
            "candidate_evaluation_complete": False,
            "next_page_available": False,
            "completion_reason": completion_reason,
            "observed_change_paths": [],
            "retrieved_record_count": 0,
            "candidate_entity_count": 0,
            "entity_fetch_count": 0,
            "accepted_signal_count": 0,
            "rejected_result_count": 0,
            "errors": page_errors,
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

    errors = [*page_errors, *entity_errors]
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
        "updates_url": initial_url,
        "lookback_days": lookback_days,
        "page_size": page_size,
        "max_update_records": max_update_records,
        "max_pages": bounded_page_limit,
        "pages_fetched": pages_fetched,
        "total_elements": total_elements,
        "retrieval_complete": retrieval_complete,
        "update_window_complete": update_window_complete,
        "candidate_evaluation_complete": candidate_evaluation_complete,
        "next_page_available": next_page_available,
        "completion_reason": completion_reason,
        "observed_change_paths": list(observed_change_paths),
        "first_update_id": min(update_ids) if update_ids else None,
        "last_update_id": max(update_ids) if update_ids else None,
        "retrieved_record_count": len(updates),
        "candidate_entity_count": len(candidates),
        "entity_fetch_count": entity_fetch_count,
        "accepted_signal_count": len(signals),
        "rejected_result_count": rejected,
        "errors": errors,
        "signals": [signals[key] for key in sorted(signals)],
        **_safety_payload(),
    }


def collect_manifest_complete_direct_official_signals(
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
    observed_at: datetime | None = None,
    json_get: JsonGetter = _default_json_get,
    text_get: TextGetter = _default_text_get,
) -> dict[str, Any]:
    """Collect all three direct sources with complete-window semantics for Norway."""
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    reports = [
        collect_brreg_complete_window_signals(observed_at=now, json_get=json_get),
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
