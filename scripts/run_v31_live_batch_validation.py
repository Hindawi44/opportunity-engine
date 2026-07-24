#!/usr/bin/env python3
"""Run V2.11 validation across a real batch, then pass results to V3.0 ranking."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.run_v211_live_opportunity_validation import build_report
from opportunity_engine.multi_opportunity_ranking import rank_evaluated_opportunities


def build_batch_report(batch: dict[str, Any]) -> dict[str, Any]:
    opportunities = batch.get("opportunities")
    opportunities = opportunities if isinstance(opportunities, list) else []
    evaluations = [build_report(item) for item in opportunities if isinstance(item, dict)]
    ranking = rank_evaluated_opportunities(evaluations, analysis_date=str(batch.get("captured_at") or ""))
    errors: list[str] = []
    if len(evaluations) != len(opportunities):
        errors.append("one or more opportunities were not objects")
    automatic = any(item.get("automatic_purchase_decision") is not False for item in evaluations)
    report = {
        "schema_version": "3.1",
        "captured_at": batch.get("captured_at"),
        "source_page": batch.get("source_page"),
        "opportunities_received": len(opportunities),
        "opportunities_evaluated": len(evaluations),
        "active_opportunities": sum((item.get("source") or {}).get("listing_status") == "ACTIVE" for item in opportunities if isinstance(item, dict)),
        "ready_for_financial_review": ranking["ready_for_financial_review"],
        "excluded_count": ranking["excluded_count"],
        "evaluations": evaluations,
        "rankings": ranking["rankings"],
        "automatic_purchase_decision": automatic,
        "errors": errors,
    }
    report["status"] = "PASS" if (
        len(evaluations) >= 3
        and not errors
        and automatic is False
        and report["ready_for_financial_review"] > 0
    ) else "IN_PROGRESS"
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", default="data/live_validation/v3.1-auksjonen-live-batch.json")
    parser.add_argument("--output", default="data/validation/v3.1-live-batch-validation.json")
    args = parser.parse_args()
    batch = json.loads(Path(args.batch).read_text(encoding="utf-8"))
    report = build_batch_report(batch)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
