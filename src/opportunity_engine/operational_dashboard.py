"""Read-only operational dashboard aggregation for Opportunity Engine V2.1."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

DECISIONS = ("BUY_REVIEW", "WATCH", "REJECT")


@dataclass(frozen=True)
class DashboardSnapshot:
    decisions: list[dict[str, Any]]
    counts: dict[str, int]
    actions: list[dict[str, Any]]
    follow_ups: list[dict[str, Any]]
    overdue_follow_ups: list[dict[str, Any]]
    health: dict[str, Any]
    learning: dict[str, Any]
    warnings: list[str]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"تعذر قراءة ملف لوحة التشغيل: {path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"ملف {path.name} يجب أن يحتوي كائن JSON.")
    return payload


def canonical_decision(item: dict[str, Any]) -> str:
    value = item.get("final_decision") or item.get("decision") or item.get("recommendation")
    normalized = str(value or "WATCH").upper()
    if normalized == "EVIDENCE_REQUIRED":
        return "WATCH"
    return normalized if normalized in DECISIONS else "WATCH"


def _records(payload: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def build_snapshot(data_dir: Path) -> DashboardSnapshot:
    decisions_payload = load_json(data_dir / "decision_intelligence.json")
    action_payload = load_json(data_dir / "action_queue.json")
    follow_payload = load_json(data_dir / "follow_up_status.json")
    health = load_json(data_dir / "discovery_health.json")
    learning = load_json(data_dir / "learning_metrics.json")

    decisions = _records(decisions_payload, "decisions", "items", "records")
    for item in decisions:
        item["canonical_decision"] = canonical_decision(item)

    computed = Counter(item["canonical_decision"] for item in decisions)
    counts = {decision: computed.get(decision, 0) for decision in DECISIONS}
    warnings: list[str] = []

    declared = {
        "BUY_REVIEW": decisions_payload.get("buy_review_count"),
        "WATCH": decisions_payload.get("watch_count"),
        "REJECT": decisions_payload.get("reject_count"),
    }
    for key, value in declared.items():
        if isinstance(value, int) and value != counts[key]:
            warnings.append(f"تعارض عداد {key}: الملف={value} والمحسوب={counts[key]}")

    actions = _records(action_payload, "queue", "actions", "items")
    follow_ups = _records(follow_payload, "records", "follow_ups", "items", "queue")
    overdue = [item for item in follow_ups if str(item.get("status", "")).upper() == "OVERDUE"]

    return DashboardSnapshot(
        decisions=decisions,
        counts=counts,
        actions=actions,
        follow_ups=follow_ups,
        overdue_follow_ups=overdue,
        health=health,
        learning=learning,
        warnings=warnings,
    )
