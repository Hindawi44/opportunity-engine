#!/usr/bin/env python3
"""Verify that every fetched official record is audited or explicitly excluded.

This is a fail-fast accounting layer. It never invents exclusion reasons from a
count difference. Only exclusions observed while reading the actual audit input
channels are accepted.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = ROOT / "scripts/build_cross_source_deduplication_audit.py"
SPEC = importlib.util.spec_from_file_location("cross_source_audit", AUDIT_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load {AUDIT_SCRIPT}")
AUDIT_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT_MODULE)

OFFICIAL_SOURCES = tuple(AUDIT_MODULE.OFFICIAL_SOURCES)
DUPLICATE_REASON = "duplicate_record_received_through_multiple_channels"


def stable_record_id(item: dict[str, Any]) -> str:
    """Return the same stable identity basis used by the audit builder."""
    record_id = AUDIT_MODULE.record_id(item)
    if record_id:
        return record_id
    canonical = AUDIT_MODULE.canonical_url(item.get("canonical_url") or item.get("url"))
    if canonical:
        return canonical
    return repr(sorted(item.items()))


def load_groups(
    daily: Path,
    discovery: Path,
    events: Path,
    channels: Path,
) -> list[tuple[str, list[dict[str, Any]]]]:
    return [
        ("daily", AUDIT_MODULE.load_items(daily)),
        ("discovery", AUDIT_MODULE.load_items(discovery)),
        (
            "bankruptcy_leads",
            AUDIT_MODULE.load_channel_items(channels, "bankruptcy_leads"),
        ),
        ("public_auction_events", AUDIT_MODULE.load_items(events)),
    ]


def collect_verified_exclusions(
    groups: list[tuple[str, list[dict[str, Any]]]],
) -> tuple[dict[str, list[dict[str, str]]], dict[str, int]]:
    """Record only exclusions observed directly while processing input records."""
    seen: set[tuple[str, str]] = set()
    excluded: dict[str, list[dict[str, str]]] = {
        source: [] for source in OFFICIAL_SOURCES
    }
    unique_input_counts = {source: 0 for source in OFFICIAL_SOURCES}

    for channel, items in groups:
        for item in items:
            source = AUDIT_MODULE.official_source_name(item)
            if source is None:
                continue
            identity = stable_record_id(item)
            key = (source, identity)
            if key in seen:
                excluded[source].append(
                    {
                        "record_id": identity,
                        "reason": DUPLICATE_REASON,
                        "channel": channel,
                    }
                )
                continue
            seen.add(key)
            unique_input_counts[source] += 1

    return excluded, unique_input_counts


def build_verified_accounting(
    audit_payload: dict[str, Any],
    funnel_counts: dict[str, int],
    groups: list[tuple[str, list[dict[str, Any]]]],
) -> dict[str, Any]:
    excluded, unique_input_counts = collect_verified_exclusions(groups)
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
        verified_records = excluded[source]
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


def apply_verified_accounting(
    audit_payload: dict[str, Any], accounting: dict[str, Any]
) -> dict[str, Any]:
    payload = dict(audit_payload)
    payload["schema_version"] = max(int(payload.get("schema_version", 0) or 0), 4)
    payload["excluded_record_count"] = accounting["excluded_record_count"]
    payload["excluded_records_by_reason"] = accounting[
        "excluded_records_by_reason"
    ]
    payload["excluded_record_ids"] = accounting["excluded_record_ids"]
    payload["verified_exclusion_accounting"] = accounting["by_source"]
    payload["verified_exclusion_accounting_valid"] = accounting["valid"]
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
    funnel_counts = AUDIT_MODULE.load_funnel_counts(Path(args.source_funnel))
    groups = load_groups(
        Path(args.daily),
        Path(args.discovery),
        Path(args.events),
        Path(args.channels),
    )
    accounting = build_verified_accounting(audit_payload, funnel_counts, groups)
    output = apply_verified_accounting(audit_payload, accounting)
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
