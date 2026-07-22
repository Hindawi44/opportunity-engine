#!/usr/bin/env python3
"""Build P5.1 action, follow-up, closure, and decision-history snapshots."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _read(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _opportunity_id(item: dict[str, Any]) -> str:
    for key in ("opportunity_id", "lead_id", "id", "canonical_url", "url"):
        value = item.get(key)
        if value:
            return str(value)
    raise ValueError("decision item has no stable opportunity identifier")


def _due_at(now: datetime, hours: int) -> str:
    return (now + timedelta(hours=hours)).isoformat()


def _next_action(item: dict[str, Any]) -> tuple[str, str, str, int]:
    decision = str(item.get("final_decision") or "WATCH")
    missing = {str(value) for value in item.get("missing_evidence", []) if value}

    if decision == "REJECT":
        return "CLOSE_OPPORTUNITY", "LOW", "SYSTEM", 0
    if decision == "BUY_REVIEW":
        return "HUMAN_BUY_REVIEW", "URGENT", "HUMAN", 2
    if "three_verified_market_comparables" in missing or "pending_market_comparables_require_review" in missing:
        return "VERIFY_MARKET_PRICE", "HIGH", "SYSTEM", 24
    if "transport_cost_nok" in missing or "transport_cost" in missing:
        return "VERIFY_TRANSPORT_COST", "HIGH", "HUMAN", 24
    if "condition_and_missing_parts" in missing:
        return "REQUEST_MORE_IMAGES", "MEDIUM", "HUMAN", 24
    return "COLLECT_MISSING_EVIDENCE", "MEDIUM", "SYSTEM", 24


def build_action_center(
    decisions_payload: dict[str, Any],
    previous_history: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    generated_at = now.isoformat()
    decisions = decisions_payload.get("decisions", [])
    if not isinstance(decisions, list):
        raise ValueError("decision_intelligence decisions must be a list")

    action_items: list[dict[str, Any]] = []
    follow_up_items: list[dict[str, Any]] = []
    closed_items: list[dict[str, Any]] = []

    old_events = []
    if isinstance(previous_history, dict) and isinstance(previous_history.get("events"), list):
        old_events = list(previous_history["events"])
    last_by_id: dict[str, dict[str, Any]] = {}
    for event in old_events:
        if isinstance(event, dict) and event.get("opportunity_id"):
            last_by_id[str(event["opportunity_id"])] = event
    new_events = list(old_events)

    for item in decisions:
        if not isinstance(item, dict):
            continue
        opportunity_id = _opportunity_id(item)
        decision = str(item.get("final_decision") or "WATCH")
        if item.get("recommendation") != decision:
            raise ValueError(f"decision inconsistency for {opportunity_id}")
        action, priority, owner, due_hours = _next_action(item)
        due_at = None if decision == "REJECT" else _due_at(now, due_hours)
        missing_ar = item.get("missing_evidence_ar", [])
        blocking_reason = "، ".join(str(v) for v in missing_ar) if missing_ar else None

        record = {
            "opportunity_id": opportunity_id,
            "title": item.get("title"),
            "url": item.get("url") or item.get("canonical_url"),
            "city": item.get("city"),
            "final_decision": decision,
            "next_action": action,
            "priority": priority,
            "owner": owner,
            "due_at": due_at,
            "blocking_reason_ar": blocking_reason,
            "maximum_safe_bid_nok": item.get("maximum_safe_bid_nok"),
            "expected_profit_nok": item.get("expected_profit_nok"),
            "roi_percent": item.get("roi_percent"),
            "requires_human_approval": bool(item.get("requires_human_approval")),
            "updated_at": generated_at,
        }

        if decision == "REJECT":
            closed_items.append({**record, "closed_at": generated_at, "close_reason_ar": "القرار النهائي رفض."})
        else:
            action_items.append(record)
            if decision == "WATCH":
                if due_at is None:
                    raise ValueError(f"WATCH opportunity {opportunity_id} has no follow-up due date")
                follow_up_items.append(record)

        previous = last_by_id.get(opportunity_id)
        if previous is None or previous.get("final_decision") != decision or previous.get("next_action") != action:
            event = {
                "opportunity_id": opportunity_id,
                "recorded_at": generated_at,
                "previous_decision": previous.get("final_decision") if previous else None,
                "final_decision": decision,
                "next_action": action,
                "reason_ar": "إنشاء الإجراء الأول" if previous is None else "تغير القرار أو الإجراء المطلوب",
            }
            new_events.append(event)
            last_by_id[opportunity_id] = event

    priority_rank = {"URGENT": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    action_items.sort(key=lambda row: (priority_rank.get(str(row["priority"]), 9), str(row["due_at"] or "")))
    follow_up_items.sort(key=lambda row: str(row["due_at"] or ""))

    action_payload = {
        "schema_version": 1,
        "generated_at": generated_at,
        "action_count": len(action_items),
        "items": action_items,
    }
    follow_payload = {
        "schema_version": 1,
        "generated_at": generated_at,
        "follow_up_count": len(follow_up_items),
        "items": follow_up_items,
    }
    closed_payload = {
        "schema_version": 1,
        "generated_at": generated_at,
        "closed_count": len(closed_items),
        "items": closed_items,
    }
    history_payload = {
        "schema_version": 1,
        "generated_at": generated_at,
        "event_count": len(new_events),
        "events": new_events[-5000:],
    }
    return action_payload, follow_payload, closed_payload, history_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build P5.1 Action Center snapshots")
    parser.add_argument("--decisions", default="data/decision_intelligence.json")
    parser.add_argument("--actions", default="data/action_queue.json")
    parser.add_argument("--follow-ups", default="data/follow_up_queue.json")
    parser.add_argument("--closed", default="data/closed_opportunities.json")
    parser.add_argument("--history", default="data/decision_history.json")
    args = parser.parse_args()

    decisions = _read(Path(args.decisions), {})
    previous_history = _read(Path(args.history), {"events": []})
    outputs = build_action_center(decisions, previous_history)
    for path, payload in zip(
        (args.actions, args.follow_ups, args.closed, args.history), outputs, strict=True
    ):
        _write(Path(path), payload)

    print(json.dumps({
        "action_count": outputs[0]["action_count"],
        "follow_up_count": outputs[1]["follow_up_count"],
        "closed_count": outputs[2]["closed_count"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
