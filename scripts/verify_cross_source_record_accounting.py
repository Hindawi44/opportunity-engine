#!/usr/bin/env python3
"""Reconcile raw fetched records with audited records and exact pipeline exclusions.

The daily runner persists raw source-document identities plus the normalized
opportunity ids used by downstream audit channels. This verifier reconciles only
the audit records backed by that exact fetch. Unrelated records from Brave or other
channels remain visible in the audit but never inflate the fetched-record equation.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LEGACY_SCRIPT = ROOT / "scripts/verify_cross_source_exclusion_accounting.py"
SPEC = importlib.util.spec_from_file_location("legacy_cross_source_accounting", LEGACY_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load {LEGACY_SCRIPT}")
LEGACY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LEGACY)

OFFICIAL_SOURCES = tuple(LEGACY.OFFICIAL_SOURCES)


def _audit_record_ids(
    groups: list[tuple[str, list[dict[str, Any]]]],
) -> dict[str, set[str]]:
    ids = {source: set() for source in OFFICIAL_SOURCES}
    for _, items in groups:
        for item in items:
            source = LEGACY.AUDIT_MODULE.official_source_name(item)
            if source is None:
                continue
            ids[source].add(LEGACY.stable_record_id(item))
    return ids


def load_pipeline_source_accounting(daily: Path) -> dict[str, dict[str, Any]]:
    if not daily.is_file():
        return {}
    payload = json.loads(daily.read_text(encoding="utf-8"))
    accounting = payload.get("source_record_accounting", {})
    sources = accounting.get("sources", {}) if isinstance(accounting, dict) else {}
    if not isinstance(sources, dict):
        return {}
    return {
        str(source): dict(row)
        for source, row in sources.items()
        if isinstance(row, dict)
    }


def load_pipeline_exclusions(
    daily: Path,
) -> dict[str, list[dict[str, str]]]:
    exclusions = {source: [] for source in OFFICIAL_SOURCES}
    sources = load_pipeline_source_accounting(daily)
    for source in OFFICIAL_SOURCES:
        row = sources.get(source, {})
        records = row.get("excluded_records", []) if isinstance(row, dict) else []
        if not isinstance(records, list):
            continue
        seen: set[str] = set()
        for record in records:
            if not isinstance(record, dict):
                continue
            record_id = str(record.get("record_id") or "").strip()
            reason = str(record.get("reason") or "").strip()
            stage = str(record.get("stage") or "").strip()
            if not record_id or not reason or record_id in seen:
                continue
            seen.add(record_id)
            exclusions[source].append(
                {
                    "record_id": record_id,
                    "reason": reason,
                    "channel": stage or "daily_pipeline",
                }
            )
    return exclusions


def _published_records(row: dict[str, Any]) -> list[dict[str, str]]:
    value = row.get("published_audit_records", [])
    records: list[dict[str, str]] = []
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            record_id = str(item.get("record_id") or "").strip()
            opportunity_id = str(item.get("opportunity_id") or "").strip()
            if record_id and opportunity_id:
                records.append(
                    {"record_id": record_id, "opportunity_id": opportunity_id}
                )
    if records:
        return records

    record_ids = row.get("published_audit_record_ids", [])
    opportunity_ids = row.get("published_audit_opportunity_ids", [])
    if not isinstance(record_ids, list):
        return []
    if not isinstance(opportunity_ids, list):
        opportunity_ids = []
    for index, raw_record_id in enumerate(record_ids):
        record_id = str(raw_record_id or "").strip()
        if not record_id:
            continue
        opportunity_id = (
            str(opportunity_ids[index] or "").strip()
            if index < len(opportunity_ids)
            else record_id
        )
        records.append(
            {
                "record_id": record_id,
                "opportunity_id": opportunity_id or record_id,
            }
        )
    return records


def _build_exact_source_row(
    source: str,
    funnel_fetched: int,
    audit_ids: set[str],
    exact_row: dict[str, Any],
    pipeline_records: list[dict[str, str]],
    observed_channel_duplicates: list[dict[str, str]],
) -> tuple[dict[str, Any], list[dict[str, str]], bool]:
    fetched_ids_value = exact_row.get("fetched_record_ids", [])
    fetched_ids = [
        str(item or "").strip()
        for item in fetched_ids_value
        if str(item or "").strip()
    ] if isinstance(fetched_ids_value, list) else []
    fetched_counter = Counter(fetched_ids)
    fetched_id_set = set(fetched_ids)
    duplicate_fetched_ids = sorted(
        record_id for record_id, count in fetched_counter.items() if count > 1
    )

    audited_fetched_ids: set[str] = set()
    matched_audit_ids: set[str] = set()
    missing_published_ids: list[str] = []

    for mapping in _published_records(exact_row):
        record_id = mapping["record_id"]
        opportunity_id = mapping["opportunity_id"]
        if opportunity_id in audit_ids:
            audited_fetched_ids.add(record_id)
            matched_audit_ids.add(opportunity_id)
        elif record_id in audit_ids:
            audited_fetched_ids.add(record_id)
            matched_audit_ids.add(record_id)
        else:
            missing_published_ids.append(record_id)

    for record_id in fetched_id_set & audit_ids:
        audited_fetched_ids.add(record_id)
        matched_audit_ids.add(record_id)

    effective_pipeline_records = [
        record
        for record in pipeline_records
        if record.get("record_id") not in audited_fetched_ids
    ]
    excluded_ids = {
        str(record.get("record_id") or "").strip()
        for record in effective_pipeline_records
        if str(record.get("record_id") or "").strip()
    }
    unexpected_exclusion_ids = sorted(excluded_ids - fetched_id_set)
    unaccounted_ids = sorted(
        fetched_id_set - audited_fetched_ids - excluded_ids
    )
    external_audit_ids = sorted(audit_ids - matched_audit_ids)

    accounted_total = len(audited_fetched_ids) + len(effective_pipeline_records)
    exact_fetched_count = len(fetched_ids)
    funnel_matches_snapshot = funnel_fetched == exact_fetched_count
    equation_holds = exact_fetched_count == accounted_total
    source_valid = (
        bool(exact_row.get("valid", False))
        and funnel_matches_snapshot
        and equation_holds
        and not duplicate_fetched_ids
        and not missing_published_ids
        and not unexpected_exclusion_ids
        and not unaccounted_ids
    )

    reason_counts = Counter(
        record["reason"] for record in effective_pipeline_records
    )
    excluded_record_ids = [
        record["record_id"] for record in effective_pipeline_records
    ]
    row = {
        "fetched_count": funnel_fetched,
        "snapshot_fetched_count": exact_fetched_count,
        "funnel_matches_snapshot": funnel_matches_snapshot,
        "audit_record_count": len(audit_ids),
        "audited_fetched_record_count": len(audited_fetched_ids),
        "audited_fetched_record_ids": sorted(audited_fetched_ids),
        "external_audit_record_count": len(external_audit_ids),
        "external_audit_record_ids": external_audit_ids,
        "observed_channel_duplicate_count": len(observed_channel_duplicates),
        "channel_duplicate_excluded_count": 0,
        "pipeline_excluded_count": len(effective_pipeline_records),
        "verified_excluded_count": len(effective_pipeline_records),
        "excluded_records_by_reason": dict(sorted(reason_counts.items())),
        "excluded_record_ids": excluded_record_ids,
        "duplicate_fetched_record_ids": duplicate_fetched_ids,
        "missing_published_record_ids": sorted(missing_published_ids),
        "unexpected_exclusion_record_ids": unexpected_exclusion_ids,
        "unaccounted_record_ids": unaccounted_ids,
        "accounted_total": accounted_total,
        "difference": exact_fetched_count - accounted_total,
        "equation_holds": equation_holds,
        "status": "RECONCILED" if source_valid else "UNEXPLAINED_LOSS",
    }
    return row, effective_pipeline_records, source_valid


def build_record_accounting(
    audit_payload: dict[str, Any],
    funnel_counts: dict[str, int],
    groups: list[tuple[str, list[dict[str, Any]]]],
    pipeline_exclusions: dict[str, list[dict[str, str]]],
    pipeline_source_accounting: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    channel_duplicates, unique_input_counts = LEGACY.collect_verified_exclusions(groups)
    audit_ids_by_source = _audit_record_ids(groups)
    audit_counts = audit_payload.get("source_record_counts", {})
    if not isinstance(audit_counts, dict):
        audit_counts = {}
    pipeline_source_accounting = pipeline_source_accounting or {}

    by_source: dict[str, dict[str, Any]] = {}
    total_excluded = 0
    all_excluded_ids: list[str] = []
    global_reason_counts: Counter[str] = Counter()
    valid = True

    for source in OFFICIAL_SOURCES:
        fetched = int(funnel_counts.get(source, 0) or 0)
        exact_row = pipeline_source_accounting.get(source)
        if isinstance(exact_row, dict) and isinstance(
            exact_row.get("fetched_record_ids"), list
        ):
            row, verified_records, source_valid = _build_exact_source_row(
                source,
                fetched,
                audit_ids_by_source[source],
                exact_row,
                pipeline_exclusions.get(source, []),
                channel_duplicates[source],
            )
            row["unique_input_record_count"] = unique_input_counts[source]
        else:
            audited = int(audit_counts.get(source, 0) or 0)
            duplicate_records = channel_duplicates[source]
            pipeline_records = [
                record
                for record in pipeline_exclusions.get(source, [])
                if record.get("record_id") not in audit_ids_by_source[source]
            ]
            verified_records = [*duplicate_records, *pipeline_records]
            verified_excluded = len(verified_records)
            expected_total = audited + verified_excluded
            equation_holds = fetched == expected_total
            source_valid = equation_holds and not (
                fetched > 0 and audited == 0 and verified_excluded == 0
            )
            reason_counts = Counter(record["reason"] for record in verified_records)
            row = {
                "fetched_count": fetched,
                "audit_record_count": audited,
                "audited_fetched_record_count": audited,
                "external_audit_record_count": 0,
                "unique_input_record_count": unique_input_counts[source],
                "observed_channel_duplicate_count": len(duplicate_records),
                "channel_duplicate_excluded_count": len(duplicate_records),
                "pipeline_excluded_count": len(pipeline_records),
                "verified_excluded_count": verified_excluded,
                "excluded_records_by_reason": dict(sorted(reason_counts.items())),
                "excluded_record_ids": [
                    record["record_id"] for record in verified_records
                ],
                "accounted_total": expected_total,
                "difference": fetched - expected_total,
                "equation_holds": equation_holds,
                "status": "RECONCILED" if source_valid else "UNEXPLAINED_LOSS",
            }

        valid = valid and source_valid
        reason_counts = Counter(record["reason"] for record in verified_records)
        global_reason_counts.update(reason_counts)
        excluded_ids = [record["record_id"] for record in verified_records]
        all_excluded_ids.extend(excluded_ids)
        total_excluded += len(verified_records)
        by_source[source] = row

    return {
        "valid": valid,
        "excluded_record_count": total_excluded,
        "excluded_records_by_reason": dict(sorted(global_reason_counts.items())),
        "excluded_record_ids": all_excluded_ids,
        "by_source": by_source,
    }


def apply_record_accounting(
    audit_payload: dict[str, Any], accounting: dict[str, Any]
) -> dict[str, Any]:
    payload = dict(audit_payload)
    payload["schema_version"] = max(int(payload.get("schema_version", 0) or 0), 6)
    payload["excluded_record_count"] = accounting["excluded_record_count"]
    payload["excluded_records_by_reason"] = accounting["excluded_records_by_reason"]
    payload["excluded_record_ids"] = accounting["excluded_record_ids"]
    payload["verified_exclusion_accounting"] = accounting["by_source"]
    payload["verified_exclusion_accounting_valid"] = accounting["valid"]
    payload["verified_source_record_accounting"] = accounting["by_source"]
    payload["verified_source_record_accounting_valid"] = accounting["valid"]
    payload["accounting_method"] = (
        "raw fetched records = audited records backed by the same fetch + exact "
        "persisted pipeline exclusions; unrelated audit-channel records are reported "
        "separately and never added to the fetched equation"
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", default="data/cross_source_deduplication_audit.json")
    parser.add_argument("--source-funnel", default="data/source_funnel.json")
    parser.add_argument("--daily", default="data/todays_opportunities.json")
    parser.add_argument("--discovery", default="data/discovery_leads.json")
    parser.add_argument("--events", default="data/public_auction_event_leads.json")
    parser.add_argument("--channels", default="data/opportunity_channels.json")
    args = parser.parse_args()

    audit_path = Path(args.audit)
    if not audit_path.is_file():
        raise SystemExit(f"Missing cross-source audit: {audit_path}")
    audit_payload = json.loads(audit_path.read_text(encoding="utf-8"))
    daily_path = Path(args.daily)
    funnel_counts = LEGACY.AUDIT_MODULE.load_funnel_counts(Path(args.source_funnel))
    groups = LEGACY.load_groups(
        daily_path,
        Path(args.discovery),
        Path(args.events),
        Path(args.channels),
    )
    accounting = build_record_accounting(
        audit_payload,
        funnel_counts,
        groups,
        load_pipeline_exclusions(daily_path),
        load_pipeline_source_accounting(daily_path),
    )
    output = apply_record_accounting(audit_payload, accounting)
    audit_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if not accounting["valid"]:
        failed = [
            source
            for source, row in accounting["by_source"].items()
            if row["status"] != "RECONCILED"
        ]
        raise SystemExit(
            "Cross-source fetched-record accounting failed for: "
            + ", ".join(failed)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
