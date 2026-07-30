#!/usr/bin/env python3
"""Reconcile raw fetched records with audited records and exact pipeline exclusions.

This verifier consumes the source-document identities persisted by the daily runner.
It does not invent exclusions from count differences. A record excluded by the sale
pipeline is ignored as an exclusion when the same source record appears in another
audited channel, such as the bankruptcy-lead channel.
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


def load_pipeline_exclusions(
    daily: Path,
) -> dict[str, list[dict[str, str]]]:
    exclusions = {source: [] for source in OFFICIAL_SOURCES}
    if not daily.is_file():
        return exclusions
    payload = json.loads(daily.read_text(encoding="utf-8"))
    accounting = payload.get("source_record_accounting", {})
    sources = accounting.get("sources", {}) if isinstance(accounting, dict) else {}
    if not isinstance(sources, dict):
        return exclusions

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


def build_record_accounting(
    audit_payload: dict[str, Any],
    funnel_counts: dict[str, int],
    groups: list[tuple[str, list[dict[str, Any]]]],
    pipeline_exclusions: dict[str, list[dict[str, str]]],
) -> dict[str, Any]:
    channel_duplicates, unique_input_counts = LEGACY.collect_verified_exclusions(groups)
    audit_ids = _audit_record_ids(groups)
    audit_counts = audit_payload.get("source_record_counts", {})
    if not isinstance(audit_counts, dict):
        audit_counts = {}

    by_source: dict[str, dict[str, Any]] = {}
    total_excluded = 0
    all_excluded_ids: list[str] = []
    global_reason_counts: Counter[str] = Counter()
    valid = True

    for source in OFFICIAL_SOURCES:
        fetched = int(funnel_counts.get(source, 0) or 0)
        audited = int(audit_counts.get(source, 0) or 0)
        duplicate_records = channel_duplicates[source]
        pipeline_records = [
            record
            for record in pipeline_exclusions.get(source, [])
            if record.get("record_id") not in audit_ids[source]
        ]
        verified_records = [*duplicate_records, *pipeline_records]
        verified_excluded = len(verified_records)
        expected_total = audited + verified_excluded
        equation_holds = fetched == expected_total
        source_valid = equation_holds and not (
            fetched > 0 and audited == 0 and verified_excluded == 0
        )
        valid = valid and source_valid

        reason_counts = Counter(record["reason"] for record in verified_records)
        global_reason_counts.update(reason_counts)
        excluded_ids = [record["record_id"] for record in verified_records]
        all_excluded_ids.extend(excluded_ids)
        total_excluded += verified_excluded

        by_source[source] = {
            "fetched_count": fetched,
            "audit_record_count": audited,
            "unique_input_record_count": unique_input_counts[source],
            "channel_duplicate_excluded_count": len(duplicate_records),
            "pipeline_excluded_count": len(pipeline_records),
            "verified_excluded_count": verified_excluded,
            "excluded_records_by_reason": dict(sorted(reason_counts.items())),
            "excluded_record_ids": excluded_ids,
            "accounted_total": expected_total,
            "difference": fetched - expected_total,
            "equation_holds": equation_holds,
            "status": "RECONCILED" if source_valid else "UNEXPLAINED_LOSS",
        }

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
    payload["schema_version"] = max(int(payload.get("schema_version", 0) or 0), 5)
    payload["excluded_record_count"] = accounting["excluded_record_count"]
    payload["excluded_records_by_reason"] = accounting["excluded_records_by_reason"]
    payload["excluded_record_ids"] = accounting["excluded_record_ids"]
    payload["verified_exclusion_accounting"] = accounting["by_source"]
    payload["verified_exclusion_accounting_valid"] = accounting["valid"]
    payload["accounting_method"] = (
        "raw fetched count = audited unique records + exact persisted pipeline exclusions "
        "+ observed duplicate channel records"
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
    funnel_counts = LEGACY.AUDIT_MODULE.load_funnel_counts(Path(args.source_funnel))
    groups = LEGACY.load_groups(
        Path(args.daily),
        Path(args.discovery),
        Path(args.events),
        Path(args.channels),
    )
    accounting = build_record_accounting(
        audit_payload,
        funnel_counts,
        groups,
        load_pipeline_exclusions(Path(args.daily)),
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
