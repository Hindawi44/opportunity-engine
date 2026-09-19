#!/usr/bin/env python3
"""Export auction-only, source-status-checked human inbox from checkpoint JSON."""
import argparse
import json
from pathlib import Path
from opportunity_engine.human_listing_review_queue import build_queue
from opportunity_engine.auction_only_review_policy import (
    restrict_to_auction_sources, require_dated_open_auction, readable_auction_review,
)
from opportunity_engine.source_status_reconciliation import reconcile_auksjonen_snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--study-memory", type=Path)
    parser.add_argument("--auksjonen-snapshot", type=Path,
                        help="Dated Auksjonen Public API snapshot; without it, unverified lots remain held")
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    memory = json.loads(args.study_memory.read_text(encoding="utf-8")) if args.study_memory else None
    queue = restrict_to_auction_sources(build_queue(report, memory))
    if args.auksjonen_snapshot and args.auksjonen_snapshot.is_file():
        snapshot = json.loads(args.auksjonen_snapshot.read_text(encoding="utf-8"))
        queue = reconcile_auksjonen_snapshot(queue, snapshot)
    else:
        queue["counts"]["auksjonen_snapshot_status"] = "MISSING_NO_ENDING_INFERRED"
    queue = require_dated_open_auction(queue)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "human-listing-review-queue-v1.json").write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "human-listing-review-queue-v1.txt").write_text(readable_auction_review(queue), encoding="utf-8")
    print(json.dumps(queue["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
