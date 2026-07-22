from __future__ import annotations

from datetime import datetime, timedelta, timezone

from scripts.build_follow_up_engine import build_follow_up_engine


def _row(opportunity_id: str, due_at: datetime) -> dict[str, object]:
    return {
        "opportunity_id": opportunity_id,
        "final_decision": "WATCH",
        "next_action": "VERIFY_MARKET_PRICE",
        "due_at": due_at.isoformat(),
        "updated_at": "2026-07-22T00:00:00+00:00",
    }


def test_pending_due_and_overdue_are_classified() -> None:
    now = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
    rows = [
        _row("pending", now + timedelta(hours=1)),
        _row("due", now - timedelta(hours=2)),
        _row("overdue", now - timedelta(hours=30)),
    ]
    actions = {"items": list(rows)}
    state, due, completed = build_follow_up_engine({"items": rows}, actions, now=now)

    statuses = {row["opportunity_id"]: row["status"] for row in state["items"]}
    assert statuses == {"pending": "PENDING", "due": "DUE", "overdue": "OVERDUE"}
    assert state["pending_count"] == 1
    assert state["due_count"] == 1
    assert state["overdue_count"] == 1
    assert due["due_work_count"] == 2
    assert completed["completed_count"] == 0


def test_review_count_increases_only_when_task_first_becomes_due() -> None:
    now = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
    row = _row("x", now - timedelta(hours=2))
    previous = {"items": [{**row, "status": "PENDING", "review_count": 0}]}
    first, _, _ = build_follow_up_engine({"items": [row]}, {"items": [row]}, previous, now)
    assert first["items"][0]["review_count"] == 1

    second, _, _ = build_follow_up_engine({"items": [row]}, {"items": [row]}, first, now + timedelta(hours=1))
    assert second["items"][0]["review_count"] == 1


def test_removed_follow_up_is_completed_not_silently_deleted() -> None:
    now = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
    previous = {
        "items": [{
            **_row("closed", now - timedelta(hours=1)),
            "status": "DUE",
            "review_count": 1,
        }]
    }
    state, due, completed = build_follow_up_engine({"items": []}, {"items": []}, previous, now)
    assert state["item_count"] == 0
    assert due["due_work_count"] == 0
    assert completed["completed_count"] == 1
    assert completed["items"][0]["status"] == "COMPLETED"


def test_invalid_due_date_fails_closed() -> None:
    row = _row("bad", datetime.now(timezone.utc))
    row["due_at"] = None
    try:
        build_follow_up_engine({"items": [row]}, {"items": [row]})
    except ValueError as exc:
        assert "no valid due_at" in str(exc)
    else:
        raise AssertionError("invalid WATCH due date must fail")
