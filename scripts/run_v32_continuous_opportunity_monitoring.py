#!/usr/bin/env python3
"""Detect newly collected opportunities and evaluate only the unseen records."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from opportunity_engine.continuous_opportunity_monitoring import (
    detect_new_opportunities,
    normalize_state,
)
from scripts.run_v31_live_batch_validation import build_batch_report


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def build_monitoring_report(
    batch: dict[str, Any],
    state_payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    opportunities = batch.get("opportunities")
    opportunities = opportunities if isinstance(opportunities, list) else []
    state = normalize_state(state_payload)
    new_records, next_state, rejected = detect_new_opportunities(
        opportunities,
        state,
        run_at=str(batch.get("captured_at") or "") or None,
    )

    new_batch = {
        "schema_version": "3.1",
        "captured_at": batch.get("captured_at"),
        "source_page": batch.get("source_page"),
        "opportunities": new_records,
    }
    evaluation = build_batch_report(new_batch) if new_records else {
        "schema_version": "3.1",
        "opportunities_received": 0,
        "opportunities_evaluated": 0,
        "active_opportunities": 0,
        "ready_for_financial_review": 0,
        "excluded_count": 0,
        "evaluations": [],
        "rankings": [],
        "automatic_purchase_decision": False,
        "errors": [],
        "status": "IN_PROGRESS",
    }

    errors = list(evaluation.get("errors") or [])
    report = {
        "schema_version": "3.2",
        "captured_at": batch.get("captured_at"),
        "source_page": batch.get("source_page"),
        "opportunities_observed": len(opportunities),
        "new_opportunities_detected": len(new_records),
        "previously_seen_count": len(opportunities) - len(new_records) - len(rejected),
        "rejected_input_count": len(rejected),
        "rejected_inputs": rejected,
        "new_opportunity_ids": [item.get("opportunity_id") for item in new_records],
        "ready_for_financial_review": int(evaluation.get("ready_for_financial_review") or 0),
        "rankings": evaluation.get("rankings") or [],
        "evaluations": evaluation.get("evaluations") or [],
        "automatic_purchase_decision": False,
        "state_advanced": len(next_state.seen_fingerprints) >= len(state.seen_fingerprints),
        "errors": errors,
    }
    if errors:
        report["status"] = "ERROR"
    elif report["ready_for_financial_review"] > 0:
        report["status"] = "REVIEW_READY"
    elif new_records:
        report["status"] = "NEW_OPPORTUNITIES_EVALUATED"
    else:
        report["status"] = "NO_NEW_OPPORTUNITIES"
    return report, next_state.to_dict()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", default="data/live_validation/v3.1-auksjonen-live-batch.json")
    parser.add_argument("--state", default="data/monitoring/v3.2-seen-state.json")
    parser.add_argument("--report", default="data/validation/v3.2-continuous-monitoring.json")
    args = parser.parse_args()

    batch = _read_json(Path(args.batch), {})
    state_path = Path(args.state)
    report, next_state = build_monitoring_report(batch, _read_json(state_path, {}))

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    state_path.write_text(json.dumps(next_state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
