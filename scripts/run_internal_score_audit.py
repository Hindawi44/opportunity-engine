#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.internal_score_audit import InternalScoreAuditor


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit internal opportunity score components and gates")
    parser.add_argument("dataset", nargs="?", default="data/todays_opportunities.json")
    parser.add_argument("--output", default="data/validation/v2.7.2.2-internal-score-audit.json")
    parser.add_argument("--required-score", type=float, default=60.0)
    args = parser.parse_args()

    auditor = InternalScoreAuditor(required_score=args.required_score)
    report = auditor.audit_file(args.dataset)
    output = auditor.write_report(report, args.output)
    print(json.dumps({
        "output": str(output),
        "records": len(report.records),
        "eligible_count": report.eligible_count,
        "below_threshold_count": report.below_threshold_count,
        "missing_score_count": report.missing_score_count,
        "component_mismatch_count": report.component_mismatch_count,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
