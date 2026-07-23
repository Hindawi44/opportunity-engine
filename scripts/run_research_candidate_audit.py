#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.research_candidate import PreliminaryResearchCandidateScorer


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit preliminary external-research candidates")
    parser.add_argument("dataset", nargs="?", default="data/todays_opportunities.json")
    parser.add_argument("--output", default="data/validation/v2.7.2.4.1-research-candidates.json")
    parser.add_argument("--threshold", type=float, default=25.0)
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()

    source = Path(args.dataset)
    payload = json.loads(source.read_text(encoding="utf-8"))
    report = PreliminaryResearchCandidateScorer(
        threshold=args.threshold,
        selection_limit=args.limit,
    ).evaluate_payload(payload)

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
