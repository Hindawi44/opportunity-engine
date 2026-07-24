#!/usr/bin/env python3
"""Produce the V2.8.1 persistent external-comparables report."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.external_comparables_accumulator import collect_persisted_comparables


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default="data/evidence")
    parser.add_argument("--output", default="data/validation/v2.8.1-external-comparables.json")
    parser.add_argument("--target-count", type=int, default=3)
    args = parser.parse_args()

    summaries = collect_persisted_comparables(args.evidence_dir, target_count=args.target_count)
    records = [summary.to_dict() for summary in summaries.values()]
    payload = {
        "schema_version": "2.8.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_comparables_per_opportunity": args.target_count,
        "opportunities_with_comparables": len(records),
        "complete_opportunities": sum(item["comparable_status"] == "COMPLETE" for item in records),
        "partial_opportunities": sum(item["comparable_status"] == "PARTIAL" for item in records),
        "verified_comparable_count": sum(item["verified_comparable_count"] for item in records),
        "records": sorted(records, key=lambda item: (-item["verified_comparable_count"], item["opportunity_id"])),
    }
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
