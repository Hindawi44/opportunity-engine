#!/usr/bin/env python3
"""Run the V2.6.6 production-readiness audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.production_readiness import ProductionReadinessAuditor


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit production readiness without exposing secrets")
    parser.add_argument("--output", default="data/production_readiness.json")
    parser.add_argument("--allow-missing-secret", action="store_true")
    parser.add_argument("--first-run", default=None)
    parser.add_argument("--second-run", default=None)
    args = parser.parse_args()

    auditor = ProductionReadinessAuditor()
    report = auditor.audit(require_live_secret=not args.allow_missing_secret)
    payload = report.to_dict()
    if args.first_run and args.second_run:
        payload["dry_run_comparison"] = auditor.inspect_dry_run(args.first_run, args.second_run)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if report.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
