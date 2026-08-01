"""Build a canonical opportunity report from completed discovery candidates."""
from __future__ import annotations

from hashlib import sha256
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from pydantic import ValidationError

from opportunity_engine.discovery.clothing_inventory_search import normalize_public_url
from opportunity_engine.discovery.unified_opportunity_adapter import (
    opportunity_record_from_discovery_candidate,
)

SCHEMA_VERSION = "1.1"


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


def _candidate_with_report_identity(candidate: Mapping[str, Any]) -> Mapping[str, Any]:
    """Add a deterministic, explicitly provisional ID without mutating input.

    Discovery identity remains authoritative. This fallback exists only so that
    rejected or incomplete candidates can be represented in the canonical
    report. It never makes a candidate identity-stable, analysis-eligible, or
    Top-5 eligible. A confirmed candidate without stable identity is downgraded
    to verification-required rather than qualified.
    """
    if _optional_text(candidate.get("opportunity_identity")) is not None:
        return candidate

    source_url = _first_source_url(candidate)
    canonical_url = normalize_public_url(source_url or "")
    if not canonical_url:
        return candidate

    provisional = dict(candidate)
    digest = sha256(canonical_url.encode("utf-8")).hexdigest()
    provisional["opportunity_identity"] = f"provisional-url-sha256:{digest}"
    provisional["identity_stable"] = False
    provisional["analysis_eligible"] = False
    provisional["top5_eligible"] = False

    state = str(candidate.get("opportunity_state") or candidate.get("state") or "")
    if state == "CONFIRMED_SALE":
        provisional["opportunity_state"] = "STRONG_LEAD_REQUIRES_VERIFICATION"
        reason = _optional_text(candidate.get("reason"))
        suffix = "stable listing identity is required before qualification"
        provisional["reason"] = f"{reason}; {suffix}" if reason else suffix

    return provisional


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
    currency: str = "NOK",
    domain: str = "TEXTILE_AND_SEWING",
) -> dict[str, Any]:
    """Convert discovery candidates independently into canonical records.

    The input discovery result is read only. Missing discovery identities use a
    deterministic provisional URL hash so rejected and incomplete candidates
    remain auditable without becoming qualified opportunities. Candidates that
    still violate the canonical contract are represented as structured
    conversion errors and never prevent valid records from being emitted.
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
            candidate_for_conversion = _candidate_with_report_identity(candidate)
            record = opportunity_record_from_discovery_candidate(
                candidate_for_conversion,
                discovered_at=timestamp,
                market_code=market_code,
                currency=currency,
                domain=domain,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            conversion_errors.append(_conversion_error(candidate, exc))
            continue
        records.append(record.model_dump(mode="json"))

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": timestamp_text,
        "market_code": market_code.upper(),
        "currency": currency.upper(),
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
    market_code: str = "NO",
    currency: str = "NOK",
    domain: str = "TEXTILE_AND_SEWING",
) -> Path:
    """Write the canonical report beside the existing discovery artifacts."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "unified-opportunity-report.json"
    report = build_unified_opportunity_report(
        result,
        generated_at=generated_at,
        market_code=market_code,
        currency=currency,
        domain=domain,
    )
    path.write_text(
        serialize_unified_opportunity_report(report) + "\n",
        encoding="utf-8",
    )
    return path
