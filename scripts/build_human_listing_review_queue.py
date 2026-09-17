#!/usr/bin/env python3
"""Export a read-only source-direct inbox from an actual checkpoint JSON."""
import argparse
import json
from pathlib import Path
from opportunity_engine.human_listing_review_queue import build_queue, readable_text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--study-memory", type=Path)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    memory = json.loads(args.study_memory.read_text(encoding="utf-8")) if args.study_memory else None
    queue = build_queue(report, memory)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "human-listing-review-queue-v1.json").write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "human-listing-review-queue-v1.txt").write_text(readable_text(queue), encoding="utf-8")
    print(json.dumps(queue["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())