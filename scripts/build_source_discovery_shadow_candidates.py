#!/usr/bin/env python3
"""Build shadow-only source candidates from a confirmed external benchmark result."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.source_discovery_shadow import build_source_shadow_candidates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--benchmark-result", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--min-independent-opportunities", type=int, default=2)
    args = parser.parse_args()

    benchmark = json.loads(Path(args.benchmark).read_text(encoding="utf-8"))
    benchmark_result = json.loads(Path(args.benchmark_result).read_text(encoding="utf-8"))
    report = build_source_shadow_candidates(
        benchmark,
        benchmark_result,
        min_independent_opportunities=args.min_independent_opportunities,
    )
    report["benchmark_path"] = Path(args.benchmark).as_posix()
    report["benchmark_result_path"] = Path(args.benchmark_result).as_posix()

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "source_candidate_count": report["source_candidate_count"],
        "validated_source_count": report["validated_source_count"],
        "shadow_eligible_source_count": report["shadow_eligible_source_count"],
        "production_mutation": report["production_mutation"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
