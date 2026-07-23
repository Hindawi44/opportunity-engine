#!/usr/bin/env python3
"""Generate V2.7.1 KPI report from a real daily-pipeline dataset."""
from __future__ import annotations

import argparse
import json

from opportunity_engine.real_opportunity_validation import RealOpportunityValidator


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate real Opportunity Engine output and emit KPI report")
    parser.add_argument("dataset", nargs="?", default="data/todays_opportunities.json")
    parser.add_argument("--output", default="data/validation/v2.7.1-real-dataset-report.json")
    parser.add_argument("--external-score-threshold", type=float, default=60.0)
    args = parser.parse_args()

    validator = RealOpportunityValidator(external_research_score_threshold=args.external_score_threshold)
    report = validator.validate_file(args.dataset)
    target = validator.write_report(report, args.output)
    response = {
        "report_path": str(target),
        "schema_version": report.schema_version,
        "duration_ms": report.duration_ms,
        "kpis": report.to_dict()["kpis"],
        "warnings": list(report.warnings),
    }
    print(json.dumps(response, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
