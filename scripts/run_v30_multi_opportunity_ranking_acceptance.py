#!/usr/bin/env python3
"""Generate one deterministic V3.0 multi-opportunity ranking acceptance report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.multi_opportunity_ranking import rank_evaluated_opportunities


def _ready(opportunity_id: str, profit: float, roi: float, quality: float, risk: str) -> dict:
    return {
        "opportunity_id": opportunity_id,
        "decision_gate": "READY_FOR_FINANCIAL_REVIEW",
        "automatic_purchase_decision": False,
        "market_evidence_status": "COMPLETE",
        "cost_evidence_status": "COMPLETE",
        "verified_comparable_count": 3,
        "verified_cost_component_count": 6,
        "expected_profit_nok": profit,
        "roi_percent": roi,
        "evidence_completeness_score": 1.0,
        "comparable_quality_score": quality,
        "risk_level": risk,
    }


def build_report() -> dict:
    records = [
        _ready("rank-test-a", 18_000, 60.0, 0.88, "LOW"),
        _ready("rank-test-b", 22_000, 44.0, 0.82, "MEDIUM"),
        _ready("rank-test-c", 26_000, 44.0, 0.91, "MEDIUM"),
        {
            "opportunity_id": "live-auksjonen-berryalloc-route66-20260724",
            "decision_gate": "EVIDENCE_REQUIRED",
            "automatic_purchase_decision": False,
            "market_evidence_status": "INCOMPLETE",
            "cost_evidence_status": "INCOMPLETE",
            "verified_comparable_count": 0,
            "verified_cost_component_count": 1,
            "expected_profit_nok": None,
            "roi_percent": None,
        },
    ]
    report = rank_evaluated_opportunities(records, analysis_date="2026-07-24T12:00:00Z")
    expected_order = ["rank-test-a", "rank-test-c", "rank-test-b"]
    errors: list[str] = []
    if [item["opportunity_id"] for item in report["rankings"]] != expected_order:
        errors.append("unexpected ranking order")
    if report["opportunities_processed"] != 4:
        errors.append("unexpected processed count")
    if report["ready_for_financial_review"] != 3:
        errors.append("unexpected eligible count")
    if report["excluded_count"] != 1:
        errors.append("unexpected excluded count")
    if report["automatic_purchase_decision"] is not False:
        errors.append("automatic purchase decision changed")
    report["errors"] = errors
    report["status"] = "PASS" if not errors else "FAIL"
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/validation/v3.0-multi-opportunity-ranking-acceptance.json")
    args = parser.parse_args()
    report = build_report()
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
