#!/usr/bin/env python3
"""Build observational P5.3 learning history and metrics without changing decisions."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _id(item: dict[str, Any]) -> str:
    for key in ("opportunity_id", "lead_id", "id", "canonical_url", "url"):
        if item.get(key):
            return str(item[key])
    raise ValueError("item has no stable opportunity identifier")


def build_learning(
    decisions_payload: dict[str, Any],
    follow_status_payload: dict[str, Any],
    completed_payload: dict[str, Any],
    previous_history: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    generated_at = now.isoformat()
    previous_records = {}
    if isinstance(previous_history, dict):
        for row in previous_history.get("records", []):
            if isinstance(row, dict) and row.get("opportunity_id"):
                previous_records[str(row["opportunity_id"])] = dict(row)

    follow_by_id = {
        _id(row): row for row in follow_status_payload.get("items", []) if isinstance(row, dict)
    }
    completed_by_id = {
        _id(row): row for row in completed_payload.get("items", []) if isinstance(row, dict)
    }

    records = dict(previous_records)
    decisions = decisions_payload.get("decisions", [])
    if not isinstance(decisions, list):
        raise ValueError("decisions must be a list")

    for item in decisions:
        if not isinstance(item, dict):
            continue
        opportunity_id = _id(item)
        decision = str(item.get("final_decision") or "WATCH")
        old = records.get(opportunity_id)
        first_observed = old.get("first_observed_at") if old else generated_at
        original_decision = old.get("original_decision") if old else decision
        record = {
            "opportunity_id": opportunity_id,
            "url": item.get("url") or item.get("canonical_url"),
            "title": item.get("title"),
            "category": item.get("category"),
            "city": item.get("city"),
            "first_observed_at": first_observed,
            "last_observed_at": generated_at,
            "original_decision": original_decision,
            "latest_decision": decision,
            "maximum_safe_bid_nok": item.get("maximum_safe_bid_nok"),
            "expected_profit_nok": item.get("expected_profit_nok"),
            "roi_percent": item.get("roi_percent"),
            "missing_evidence": list(item.get("missing_evidence", [])),
            "outcome_status": "OBSERVING",
            "outcome_verified": False,
        }
        if opportunity_id in follow_by_id:
            record["follow_up_status"] = follow_by_id[opportunity_id].get("status")
            record["review_count"] = follow_by_id[opportunity_id].get("review_count", 0)
        if opportunity_id in completed_by_id:
            record["outcome_status"] = "FOLLOW_UP_COMPLETED"
            record["completed_at"] = completed_by_id[opportunity_id].get("completed_at")
        records[opportunity_id] = record

    ordered = sorted(records.values(), key=lambda row: str(row["opportunity_id"]))
    decisions_count = Counter(str(row.get("latest_decision") or "UNKNOWN") for row in ordered)
    missing_count = Counter(
        str(value) for row in ordered for value in row.get("missing_evidence", []) if value
    )
    profits = [float(row["expected_profit_nok"]) for row in ordered if isinstance(row.get("expected_profit_nok"), (int, float))]
    bids = [float(row["maximum_safe_bid_nok"]) for row in ordered if isinstance(row.get("maximum_safe_bid_nok"), (int, float))]

    history = {
        "schema_version": 1,
        "generated_at": generated_at,
        "mode": "OBSERVATION_ONLY",
        "automatic_weight_updates": False,
        "record_count": len(ordered),
        "records": ordered,
    }
    metrics = {
        "schema_version": 1,
        "generated_at": generated_at,
        "mode": "OBSERVATION_ONLY",
        "automatic_weight_updates": False,
        "total_opportunities": len(ordered),
        "decision_counts": dict(sorted(decisions_count.items())),
        "verified_outcome_count": sum(1 for row in ordered if row.get("outcome_verified") is True),
        "average_expected_profit_nok": round(sum(profits) / len(profits), 2) if profits else None,
        "average_maximum_safe_bid_nok": round(sum(bids) / len(bids), 2) if bids else None,
        "top_missing_evidence": [
            {"evidence": key, "count": count} for key, count in missing_count.most_common(10)
        ],
        "weight_change_recommendations": [],
        "learning_status": "INSUFFICIENT_VERIFIED_OUTCOMES" if not any(row.get("outcome_verified") for row in ordered) else "OBSERVING",
    }
    return history, metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Build safe observational P5.3 learning snapshots")
    parser.add_argument("--decisions", default="data/decision_intelligence.json")
    parser.add_argument("--follow-status", default="data/follow_up_status.json")
    parser.add_argument("--completed", default="data/completed_follow_ups.json")
    parser.add_argument("--history", default="data/learning_history.json")
    parser.add_argument("--metrics", default="data/learning_metrics.json")
    args = parser.parse_args()
    history, metrics = build_learning(
        _read(Path(args.decisions), {}),
        _read(Path(args.follow_status), {}),
        _read(Path(args.completed), {}),
        _read(Path(args.history), {"records": []}),
    )
    _write(Path(args.history), history)
    _write(Path(args.metrics), metrics)
    print(json.dumps({"record_count": history["record_count"], "learning_status": metrics["learning_status"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
