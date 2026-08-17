#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from opportunity_engine.discovery.keyword_discovery_lab import run_keyword_discovery_lab


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the bounded shadow keyword discovery lab."
    )
    parser.add_argument(
        "--output",
        default="artifacts/keyword-discovery-lab/keyword-lab-report.json",
        help="JSON report output path",
    )
    parser.add_argument("--keyword-limit", type=int, default=10)
    parser.add_argument("--results-per-keyword", type=int, default=5)
    parser.add_argument(
        "--freshness",
        choices=("none", "pd", "pw", "pm", "py"),
        default="none",
    )
    args = parser.parse_args()

    freshness = None if args.freshness == "none" else args.freshness
    report = run_keyword_discovery_lab(
        environment=os.environ,
        keyword_limit=args.keyword_limit,
        results_per_keyword=args.results_per_keyword,
        freshness=freshness,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = {
        "status": report.get("status"),
        "queries_attempted": report.get("queries_attempted", 0),
        "queries_succeeded": report.get("queries_succeeded", 0),
        "promote_count": report.get("promote_count", 0),
        "shadow_count": report.get("shadow_count", 0),
        "reject_count": report.get("reject_count", 0),
        "error_count": report.get("error_count", 0),
        "output": output.as_posix(),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))

    status = report.get("status")
    return 2 if status in {"BLOCKED_CONFIGURATION", "BLOCKED_RETRIEVAL"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
