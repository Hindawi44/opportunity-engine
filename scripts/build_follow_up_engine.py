#!/usr/bin/env python3
"""Build P5.2 follow-up lifecycle, due-work, and completion snapshots.

The engine is deliberately conservative: it never marks a business task completed
unless the canonical decision or action state proves it is closed/replaced. Time
alone can only move a task from PENDING to DUE or OVERDUE.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
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


def _parse_time(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        result = datetime.fromisoformat(text)
    except ValueError:
        return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _stable_id(item: dict[str, Any]) -> str:
    for key in ("opportunity_id", "lead_id", "id", "canonical_url", "url"):
        if item.get(key):
            return str(item[key])
    raise ValueError("follow-up item has no stable identifier")


def _previous_by_id(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    rows = payload.get("items", []) if isinstance(payload, dict) else []
    return {
        str(row["opportunity_id"]): row
        for row in rows
        if isinstance(row, dict) and row.get("opportunity_id")
    }


def build_follow_up_engine(
    follow_up_payload: dict[str, Any],
    action_payload: dict[str, Any],
    previous_state: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    generated_at = now.isoformat()

    follow_rows = follow_up_payload.get("items", [])
    action_rows = action_payload.get("items", [])
    if not isinstance(follow_rows, list) or not isinstance(action_rows, list):
        raise ValueError("action and follow-up items must be lists")

    active_actions = {
        _stable_id(row): row for row in action_rows if isinstance(row, dict)
    }
    previous = _previous_by_id(previous_state)
    lifecycle: list[dict[str, Any]] = []
    due_work: list[dict[str, Any]] = []
    completed: list[dict[str, Any]] = []

    current_ids: set[str] = set()
    for row in follow_rows:
        if not isinstance(row, dict):
            continue
        opportunity_id = _stable_id(row)
        current_ids.add(opportunity_id)
        due_at = _parse_time(row.get("due_at"))
        if due_at is None:
            raise ValueError(f"WATCH follow-up {opportunity_id} has no valid due_at")

        age_hours = max(0.0, (now - due_at).total_seconds() / 3600.0)
        if now < due_at:
            status = "PENDING"
        elif age_hours < 24:
            status = "DUE"
        else:
            status = "OVERDUE"

        old = previous.get(opportunity_id, {})
        review_count = int(old.get("review_count") or 0)
        if status in {"DUE", "OVERDUE"} and old.get("status") not in {"DUE", "OVERDUE"}:
            review_count += 1

        record = dict(row)
        record.update({
            "follow_up_status": status,
            "status": status,
            "review_count": review_count,
            "first_scheduled_at": old.get("first_scheduled_at") or row.get("updated_at") or generated_at,
            "last_evaluated_at": generated_at,
            "overdue_hours": round(age_hours, 2) if status == "OVERDUE" else 0.0,
            "completion_is_automatic": False,
        })
        lifecycle.append(record)
        if status in {"DUE", "OVERDUE"}:
            due_work.append(record)

    # A formerly tracked task is complete only when it is no longer a WATCH
    # follow-up and the canonical action queue confirms closure/replacement.
    for opportunity_id, old in previous.items():
        if opportunity_id in current_ids:
            continue
        current_action = active_actions.get(opportunity_id)
        final_decision = str((current_action or {}).get("final_decision") or old.get("final_decision") or "")
        reason = "الفرصة لم تعد ضمن قائمة المتابعة النشطة."
        if final_decision == "BUY_REVIEW":
            reason = "تحولت الفرصة من المراقبة إلى مراجعة شراء بشرية."
        elif final_decision == "REJECT" or current_action is None:
            reason = "أغلقت الفرصة أو خرجت من قائمة الإجراءات النشطة."
        completed.append({
            **old,
            "status": "COMPLETED",
            "follow_up_status": "COMPLETED",
            "completed_at": generated_at,
            "completion_reason_ar": reason,
        })

    rank = {"OVERDUE": 0, "DUE": 1, "PENDING": 2}
    lifecycle.sort(key=lambda row: (rank.get(str(row.get("status")), 9), str(row.get("due_at") or "")))
    due_work.sort(key=lambda row: (rank.get(str(row.get("status")), 9), str(row.get("due_at") or "")))

    state_payload = {
        "schema_version": 1,
        "generated_at": generated_at,
        "item_count": len(lifecycle),
        "pending_count": sum(row["status"] == "PENDING" for row in lifecycle),
        "due_count": sum(row["status"] == "DUE" for row in lifecycle),
        "overdue_count": sum(row["status"] == "OVERDUE" for row in lifecycle),
        "items": lifecycle,
    }
    due_payload = {
        "schema_version": 1,
        "generated_at": generated_at,
        "due_work_count": len(due_work),
        "items": due_work,
    }
    completed_payload = {
        "schema_version": 1,
        "generated_at": generated_at,
        "completed_count": len(completed),
        "items": completed,
    }
    return state_payload, due_payload, completed_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build P5.2 follow-up lifecycle snapshots")
    parser.add_argument("--follow-ups", default="data/follow_up_queue.json")
    parser.add_argument("--actions", default="data/action_queue.json")
    parser.add_argument("--state", default="data/follow_up_status.json")
    parser.add_argument("--due-work", default="data/follow_up_due.json")
    parser.add_argument("--completed", default="data/completed_follow_ups.json")
    args = parser.parse_args()

    follow_ups = _read(Path(args.follow_ups), {"items": []})
    actions = _read(Path(args.actions), {"items": []})
    previous = _read(Path(args.state), {"items": []})
    outputs = build_follow_up_engine(follow_ups, actions, previous)
    for path, payload in zip((args.state, args.due_work, args.completed), outputs, strict=True):
        _write(Path(path), payload)

    print(json.dumps({
        "follow_up_count": outputs[0]["item_count"],
        "due_count": outputs[0]["due_count"],
        "overdue_count": outputs[0]["overdue_count"],
        "completed_count": outputs[2]["completed_count"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
