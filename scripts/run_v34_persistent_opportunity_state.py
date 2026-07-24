#!/usr/bin/env python3
"""Compare a refreshed snapshot with persistent lifecycle state and evaluate changes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from opportunity_engine.persistent_opportunity_state import (
    actionable_records,
    compare_snapshot,
)
from scripts.run_v32_continuous_opportunity_monitoring import build_monitoring_report


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def build_lifecycle_report(
    snapshot: dict[str, Any],
    lifecycle_state: dict[str, Any] | None = None,
    monitoring_state: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    opportunities = snapshot.get("opportunities")
    opportunities = opportunities if isinstance(opportunities, list) else []
    observed_at = str(snapshot.get("captured_at") or "") or None
    events, next_lifecycle_state = compare_snapshot(
        opportunities,
        lifecycle_state,
        observed_at=observed_at,
    )
    actionable = actionable_records(events)
    changed_batch = {
        "schema_version": "3.1",
        "captured_at": observed_at,
        "source_page": snapshot.get("source_page"),
        "opportunities": actionable,
    }
    monitoring_report, next_monitoring_state = build_monitoring_report(
        changed_batch,
        monitoring_state,
    )
    counts = {
        status: sum(event.get("lifecycle_status") == status for event in events)
        for status in ("NEW", "UPDATED", "UNCHANGED", "REMOVED", "ARCHIVED")
    }
    errors = list(monitoring_report.get("errors") or [])
    report = {
        "schema_version": "3.4",
        "captured_at": observed_at,
        "source_page": snapshot.get("source_page"),
        "opportunities_observed": len(opportunities),
        "lifecycle_counts": counts,
        "events": events,
        "actionable_count": len(actionable),
        "actionable_opportunity_ids": [event["opportunity_id"] for event in events if event.get("lifecycle_status") in {"NEW", "UPDATED"}],
        "passed_to_v3_2": int(monitoring_report.get("new_opportunities_detected") or 0),
        "monitoring_report": monitoring_report,
        "automatic_purchase_decision": False,
        "errors": errors,
        "status": "ERROR" if errors else "PASS",
    }
    return report, next_lifecycle_state, next_monitoring_state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", default="data/live_validation/v3.3-auksjonen-live-snapshot.json")
    parser.add_argument("--lifecycle-state", default="data/monitoring/v3.4-lifecycle-state.json")
    parser.add_argument("--monitoring-state", default="data/monitoring/v3.2-seen-state.json")
    parser.add_argument("--report", default="data/validation/v3.4-persistent-opportunity-state.json")
    args = parser.parse_args()

    snapshot = _read_json(Path(args.snapshot), {})
    lifecycle_path = Path(args.lifecycle_state)
    monitoring_path = Path(args.monitoring_state)
    report, lifecycle_state, monitoring_state = build_lifecycle_report(
        snapshot,
        _read_json(lifecycle_path, {}),
        _read_json(monitoring_path, {}),
    )

    report_path = Path(args.report)
    for path in (report_path, lifecycle_path, monitoring_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lifecycle_path.write_text(json.dumps(lifecycle_state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    monitoring_path.write_text(json.dumps(monitoring_state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
