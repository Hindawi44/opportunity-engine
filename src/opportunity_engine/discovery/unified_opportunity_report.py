"""Build a canonical opportunity report from completed discovery candidates."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from pydantic import ValidationError

from opportunity_engine.discovery.unified_opportunity_adapter import (
    opportunity_record_from_discovery_candidate,
)

SCHEMA_VERSION = "1.0"


def _utc_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_source_url(candidate: Mapping[str, Any]) -> str | None:
    urls = candidate.get("source_urls")
    if not isinstance(urls, Sequence) or isinstance(urls, (str, bytes)) or not urls:
        return None
    return _optional_text(urls[0])


def _conversion_error(candidate: object, exc: Exception) -> dict[str, str | None]:
    if isinstance(candidate, Mapping):
        title = _optional_text(candidate.get("title"))
        source_url = _first_source_url(candidate)
        opportunity_identity = _optional_text(candidate.get("opportunity_identity"))
    else:
        title = None
        source_url = None
        opportunity_identity = None

    return {
        "title": title,
        "source_url": source_url,
        "opportunity_identity": opportunity_identity,
        "reason": f"{type(exc).__name__}: {exc}",
    }


def build_unified_opportunity_report(
    result: Mapping[str, Any],
    *,
    generated_at: datetime | None = None,
    market_code: str = "NO",
    domain: str = "TEXTILE_AND_SEWING",
) -> dict[str, Any]:
    """Convert discovery candidates independently into canonical records.

    The input discovery result is read only. Invalid candidates are represented
    as structured conversion errors and never prevent valid records from being
    emitted.
    """
    candidates = result.get("all_discovered_candidates")
    if not isinstance(candidates, list):
        raise ValueError("all_discovered_candidates must be a list")

    timestamp = generated_at or datetime.now(timezone.utc)
    timestamp_text = _utc_timestamp(timestamp)
    records: list[dict[str, Any]] = []
    conversion_errors: list[dict[str, str | None]] = []

    for candidate in candidates:
        try:
            if not isinstance(candidate, Mapping):
                raise TypeError("discovery candidate must be an object")
            record = opportunity_record_from_discovery_candidate(
                candidate,
                discovered_at=timestamp,
                market_code=market_code,
                domain=domain,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            conversion_errors.append(_conversion_error(candidate, exc))
            continue
        records.append(record.model_dump(mode="json"))

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": timestamp_text,
        "record_count": len(records),
        "records": records,
        "conversion_error_count": len(conversion_errors),
        "conversion_errors": conversion_errors,
    }


def serialize_unified_opportunity_report(report: Mapping[str, Any]) -> str:
    """Return stable, human-readable JSON for one canonical report."""
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def write_unified_opportunity_report(
    result: Mapping[str, Any],
    output_dir: str | Path,
    *,
    generated_at: datetime | None = None,
) -> Path:
    """Write the canonical report beside the existing discovery artifacts."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "unified-opportunity-report.json"
    report = build_unified_opportunity_report(result, generated_at=generated_at)
    path.write_text(
        serialize_unified_opportunity_report(report) + "\n",
        encoding="utf-8",
    )
    return path
