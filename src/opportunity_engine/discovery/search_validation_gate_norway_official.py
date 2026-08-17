"""Offline Search Validation Gate extension for Norway's official auction sources.

This module keeps the V1.1 integrity policy unchanged while adding evidence from
Norwegian public-source adapters that already produce canonical ACTIVE records:
Vareauksjonen and Auksjoner.no. It reads saved JSON artifacts only and performs
no network, paid-search, AI, contact, bid, purchase, or payment action.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

from opportunity_engine.discovery.search_validation_gate import (
    CORE_MARKETS,
    SearchObservation,
    build_search_validation_report as _build_v1_report,
)
from opportunity_engine.discovery.search_validation_gate_integrity import (
    SearchValidationIntegrityPolicy,
    collect_verified_active_identities,
    load_integrity_observations,
    _recompute_market_and_overall,
)

ENGINE_VERSION = "SEARCH_VALIDATION_GATE_V1_2_NORWAY_OFFICIAL_SOURCES"

_OFFICIAL_SOURCES: dict[str, dict[str, Any]] = {
    "vareauksjonen-live-clothing-listings.json": {
        "source_name": "Vareauksjonen Public Pages",
        "records_key": "listings",
        "raw_count_keys": ("candidate_count", "detail_pages_requested"),
        "accepted_count_key": "inventory_opportunity_count",
    },
    "auksjoner-no-live-clothing-auctions.json": {
        "source_name": "Auksjoner.no Current Auctions",
        "records_key": "auctions",
        "raw_count_keys": ("items_received",),
        "accepted_count_key": "inventory_opportunity_count",
    },
}


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < 0:
        return None
    return int(value)


def _first_int(payload: Mapping[str, Any], keys: Sequence[str]) -> int | None:
    for key in keys:
        value = _nonnegative_int(payload.get(key))
        if value is not None:
            return value
    return None


def _records(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _is_verified_active_inventory(record: Mapping[str, Any]) -> bool:
    return (
        _compact(record.get("listing_status")).upper() == "ACTIVE"
        and record.get("clothing_signal") is True
        and record.get("inventory_lot_signal") is True
    )


def _observed_at(payload: Mapping[str, Any]) -> str | None:
    for key in ("captured_at", "generated_at", "executed_at", "observed_at"):
        value = _compact(payload.get(key))
        if value:
            return value
    return None


def _execution_status(payload: Mapping[str, Any]) -> str:
    errors = payload.get("errors")
    if isinstance(errors, list) and errors:
        return "PARTIAL_RETRIEVAL"
    if payload.get("scan_complete") is False:
        return "PARTIAL_RETRIEVAL"
    return "SUCCESS"


def _official_observation(
    payload: Mapping[str, Any],
    path: Path,
    run_label: str,
) -> SearchObservation | None:
    spec = _OFFICIAL_SOURCES.get(path.name)
    if spec is None:
        return None
    rows = _records(payload, str(spec["records_key"]))
    verified = [row for row in rows if _is_verified_active_inventory(row)]
    accepted = _nonnegative_int(payload.get(str(spec["accepted_count_key"]))) or 0
    accepted = max(accepted, len(verified))
    return SearchObservation(
        run_label=run_label,
        artifact_path=path.as_posix(),
        observed_at=_observed_at(payload),
        market_code="NO",
        source_name=str(spec["source_name"]),
        execution_status=_execution_status(payload),
        queries_attempted=None,
        queries_succeeded=None,
        paid_search=False,
        paid_requests_made=0,
        raw_hits=_first_int(payload, tuple(spec["raw_count_keys"])),
        accepted_leads=accepted,
        rejected_results=None,
        ended_or_historical=0,
        verified_active_leads=len(verified),
        actionable_leads=len(verified),
    )


def _candidate_paths(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.name in _OFFICIAL_SOURCES else []
    return sorted(
        path for path in root.rglob("*.json") if path.name in _OFFICIAL_SOURCES
    )


def load_norway_official_observations(
    run_dirs: Sequence[str | Path],
) -> list[SearchObservation]:
    """Load Vareauksjonen/Auksjoner.no saved artifacts without external calls."""
    rows: list[SearchObservation] = []
    seen: set[tuple[str, str, str, str | None]] = set()
    for raw_root in run_dirs:
        root = Path(raw_root)
        run_label = root.name
        for path in _candidate_paths(root):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, Mapping):
                continue
            item = _official_observation(payload, path, run_label)
            if item is None:
                continue
            key = (
                item.run_label,
                item.source_name,
                item.artifact_path,
                item.observed_at,
            )
            if key in seen:
                continue
            seen.add(key)
            rows.append(item)
    return rows


def _canonical_url(value: object) -> str | None:
    text = _compact(value)
    if not text.startswith(("http://", "https://")):
        return None
    parsed = urlsplit(text)
    if not parsed.netloc:
        return None
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def _official_identity(record: Mapping[str, Any]) -> str | None:
    listing_id = record.get("listing_id")
    if isinstance(listing_id, (int, str)) and _compact(listing_id):
        return f"listing_id:{_compact(listing_id)}"
    auction_id = record.get("auction_id")
    if isinstance(auction_id, (int, str)) and _compact(auction_id):
        return f"auction_id:{_compact(auction_id)}"
    return _canonical_url(record.get("url") or record.get("source_url"))


def collect_norway_official_identities(
    run_dirs: Sequence[str | Path],
) -> dict[tuple[str, str], dict[str, set[str]]]:
    """Collect distinct canonical ACTIVE inventory identities per Norway source."""
    result: dict[tuple[str, str], dict[str, set[str]]] = {}
    for raw_root in run_dirs:
        root = Path(raw_root)
        run_label = root.name
        for path in _candidate_paths(root):
            spec = _OFFICIAL_SOURCES[path.name]
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, Mapping):
                continue
            key = ("NO", str(spec["source_name"]))
            bucket = result.setdefault(key, {}).setdefault(run_label, set())
            for record in _records(payload, str(spec["records_key"])):
                if not _is_verified_active_inventory(record):
                    continue
                identity = _official_identity(record)
                if identity:
                    bucket.add(identity)
    return result


def _merge_identity_maps(
    base: dict[tuple[str, str], dict[str, set[str]]],
    extra: dict[tuple[str, str], dict[str, set[str]]],
) -> dict[tuple[str, str], dict[str, set[str]]]:
    merged: dict[tuple[str, str], dict[str, set[str]]] = {
        key: {run: set(ids) for run, ids in run_map.items()}
        for key, run_map in base.items()
    }
    for key, run_map in extra.items():
        target = merged.setdefault(key, {})
        for run, ids in run_map.items():
            target.setdefault(run, set()).update(ids)
    return merged


def build_norway_official_search_validation_report(
    run_dirs: Sequence[str | Path],
    *,
    policy: SearchValidationIntegrityPolicy | None = None,
    required_markets: Sequence[str] = CORE_MARKETS,
) -> dict[str, Any]:
    """Build V1.1-equivalent integrity report plus Norway official-source evidence."""
    policy = policy or SearchValidationIntegrityPolicy()
    base_observations = load_integrity_observations(run_dirs)
    official_observations = load_norway_official_observations(run_dirs)
    observations = [*base_observations, *official_observations]

    report = _build_v1_report(
        observations,
        policy=policy.base_policy(),
        required_markets=required_markets,
    )

    base_identities = collect_verified_active_identities(run_dirs, base_observations)
    official_identities = collect_norway_official_identities(run_dirs)
    identity_map = _merge_identity_maps(base_identities, official_identities)

    for source in report.get("sources") or []:
        if not isinstance(source, dict):
            continue
        key = (
            str(source.get("market_code") or ""),
            str(source.get("source_name") or ""),
        )
        run_map = identity_map.get(key, {})
        distinct = sorted({identity for ids in run_map.values() for identity in ids})
        source["verified_active_identities_by_run"] = {
            run: sorted(ids) for run, ids in sorted(run_map.items())
        }
        source["distinct_verified_active_identity_count"] = len(distinct)
        source["distinct_verified_active_identities"] = distinct

        verified_count = int(source.get("verified_active_lead_count") or 0)
        if verified_count > 0 and not distinct:
            reasons = list(source.get("reasons") or [])
            if "VERIFIED_ACTIVE_IDENTITY_ACCOUNTING_INCOMPLETE" not in reasons:
                reasons.append("VERIFIED_ACTIVE_IDENTITY_ACCOUNTING_INCOMPLETE")
            source["reasons"] = reasons
            source["verdict"] = "INSUFFICIENT_EVIDENCE"
        elif (
            source.get("verdict") == "PROVEN"
            and len(distinct) < policy.min_distinct_verified_active_leads
        ):
            reasons = list(source.get("reasons") or [])
            if "DISTINCT_VERIFIED_ACTIVE_LEADS_NOT_PROVEN" not in reasons:
                reasons.append("DISTINCT_VERIFIED_ACTIVE_LEADS_NOT_PROVEN")
            source["reasons"] = reasons
            source["verdict"] = "NOT_PROVEN"

    report["engine_version"] = ENGINE_VERSION
    report["policy"] = policy.to_dict()
    report["integrity_correction"] = {
        "legacy_query_statusless_diagnostics_supported": True,
        "distinct_verified_active_identity_required": True,
        "same_listing_repeated_across_days_is_not_distinct_proof": True,
        "norway_official_sources_supported": [
            "Auksjonen Public API",
            "Vareauksjonen Public Pages",
            "Auksjoner.no Current Auctions",
        ],
        "external_api_calls": False,
        "brave_requests": 0,
    }
    _recompute_market_and_overall(report)
    return report
