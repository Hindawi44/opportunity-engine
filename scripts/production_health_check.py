#!/usr/bin/env python3
"""Run production readiness checks and return a CI-friendly exit code."""

from __future__ import annotations

import argparse
import json

from opportunity_engine.ods.production_health import ProductionHealthChecker


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Opportunity Engine production readiness")
    parser.add_argument("--data-directory", default="data")
    parser.add_argument("--output", default="data/health_report.json")
    args = parser.parse_args()

    report = ProductionHealthChecker().write_report(
        args.output,
        data_directory=args.data_directory,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0 if report.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
