#!/usr/bin/env python3
"""Audit persisted investment files and evidence across workflow runs."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _snapshot(root: Path) -> dict[str, Any]:
    evidence_files = sorted((root / "evidence").glob("*.json"))
    living_files = sorted((root / "investment_files").glob("*.json"))
    payload = _read(root / "opportunity_evidence.json", {})
    records = payload.get("evidence", {}) if isinstance(payload, dict) else {}
    comparable_count = 0
    duplicate_count = 0
    opportunity_count = 0
    if isinstance(records, dict):
        opportunity_count = len(records)
        for record in records.values():
            if not isinstance(record, dict):
                continue
            comparables = record.get("market_comparables", [])
            if not isinstance(comparables, list):
                continue
            comparable_count += len(comparables)
            seen: set[tuple[str, float]] = set()
            for item in comparables:
                if not isinstance(item, dict):
                    continue
                key = (str(item.get("url") or ""), float(item.get("price_nok") or 0.0))
                if key in seen:
                    duplicate_count += 1
                seen.add(key)
    return {
        "evidence_file_count": len(evidence_files),
        "living_file_count": len(living_files),
        "opportunity_evidence_count": opportunity_count,
        "verified_comparable_count": comparable_count,
        "duplicate_comparable_count": duplicate_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("baseline", "final"), required=True)
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--baseline", default="data/validation/v2.7.3-persistence-baseline.json")
    parser.add_argument("--output", default="data/validation/v2.7.3-evidence-persistence.json")
    args = parser.parse_args()

    root = Path(args.data_root)
    baseline_path = Path(args.baseline)
    current = _snapshot(root)

    if args.phase == "baseline":
        payload = {
            "schema_version": "2.7.3",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "cache_hit": os.getenv("PERSISTENCE_CACHE_HIT", "false").lower() == "true",
            **current,
        }
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    baseline = _read(baseline_path, {})
    previous_evidence = int(baseline.get("evidence_file_count", 0)) if isinstance(baseline, dict) else 0
    previous_living = int(baseline.get("living_file_count", 0)) if isinstance(baseline, dict) else 0
    previous_comparables = int(baseline.get("verified_comparable_count", 0)) if isinstance(baseline, dict) else 0
    cache_hit = bool(baseline.get("cache_hit", False)) if isinstance(baseline, dict) else False

    report = {
        "schema_version": "2.7.3",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "loaded_previous_file": cache_hit and previous_living > 0,
        "previous_evidence_loaded": cache_hit and (previous_evidence > 0 or previous_comparables > 0),
        "new_evidence_merged": current["verified_comparable_count"] >= previous_comparables,
        "duplicate_evidence_removed": current["duplicate_comparable_count"] == 0,
        "living_file_saved": current["living_file_count"] > 0,
        "evidence_survived_next_run": cache_hit and (previous_evidence > 0 or previous_comparables > 0),
        "baseline": baseline,
        "final": current,
        "delta": {
            "evidence_files": current["evidence_file_count"] - previous_evidence,
            "living_files": current["living_file_count"] - previous_living,
            "verified_comparables": current["verified_comparable_count"] - previous_comparables,
        },
        "status": "PASS" if current["duplicate_comparable_count"] == 0 and current["living_file_count"] > 0 else "INCOMPLETE",
        "note": "evidence_survived_next_run can only become true on the second successful workflow run.",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
