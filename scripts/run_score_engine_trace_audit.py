#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from opportunity_engine.score_engine_trace import ScoreEngineTraceAuditor


def main() -> int:
    parser = argparse.ArgumentParser(description="Trace scoring invocation, components and dataset serialization")
    parser.add_argument("dataset", nargs="?", default="data/todays_opportunities.json")
    parser.add_argument("--output", default="data/validation/v2.7.2.3-score-engine-trace.json")
    args = parser.parse_args()

    auditor = ScoreEngineTraceAuditor()
    report = auditor.audit_file(args.dataset)
    output = auditor.write_report(report, args.output)
    print(json.dumps({
        "output": str(output),
        "record_count": report.record_count,
        "scoring_function_called_count": report.scoring_function_called_count,
        "breakdown_serialized_count": report.breakdown_serialized_count,
        "missing_breakdown_count": report.missing_breakdown_count,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
