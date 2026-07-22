from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

ALERTABLE_TRANSITIONS = {
    ("WATCH", "BUY_REVIEW"),
    ("BUY_REVIEW", "REJECT"),
    ("BUY_REVIEW", "WATCH"),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decision(item: dict[str, Any]) -> str:
    value = item.get("final_decision") or item.get("recommendation") or item.get("decision") or "WATCH"
    return "WATCH" if value == "EVIDENCE_REQUIRED" else str(value)


def _fingerprint(opportunity_id: str, event_type: str, old: str | None, new: str) -> str:
    return f"{opportunity_id}|{event_type}|{old or '-'}|{new}"


def _message(item: dict[str, Any], event_type: str, old: str | None, new: str) -> str:
    title = str(item.get("title") or item.get("opportunity_id") or "فرصة جديدة").strip()
    city = str(item.get("city") or "").strip()
    score = item.get("opportunity_score")
    price = item.get("asking_price_nok")
    prefix = "🔔 فرصة قوية جديدة" if event_type == "NEW_STRONG_OPPORTUNITY" else f"🔄 تغير القرار: {old} ← {new}"
    parts = [prefix, title]
    if city:
        parts.append(f"📍 {city}")
    if isinstance(price, (int, float)):
        parts.append(f"💰 {price:,.0f} NOK")
    if isinstance(score, (int, float)):
        parts.append(f"⭐ {score:.1f}/100")
    return "\n".join(parts)


def build_smart_alerts(
    decisions: list[dict[str, Any]],
    previous_state: dict[str, str] | None = None,
    sent_fingerprints: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, str], set[str]]:
    previous_state = dict(previous_state or {})
    sent_fingerprints = set(sent_fingerprints or set())
    alerts: list[dict[str, Any]] = []
    current_state: dict[str, str] = {}

    for item in decisions:
        opportunity_id = str(item.get("opportunity_id") or "").strip()
        if not opportunity_id:
            continue
        new_decision = _decision(item)
        old_decision = previous_state.get(opportunity_id)
        current_state[opportunity_id] = new_decision

        event_type: str | None = None
        if old_decision is None and new_decision == "BUY_REVIEW":
            event_type = "NEW_STRONG_OPPORTUNITY"
        elif old_decision is not None and old_decision != new_decision and (old_decision, new_decision) in ALERTABLE_TRANSITIONS:
            event_type = "DECISION_CHANGED"

        if event_type is None:
            continue

        fingerprint = _fingerprint(opportunity_id, event_type, old_decision, new_decision)
        if fingerprint in sent_fingerprints:
            continue

        alerts.append({
            "alert_id": fingerprint,
            "created_at": _now_iso(),
            "event_type": event_type,
            "opportunity_id": opportunity_id,
            "old_decision": old_decision,
            "new_decision": new_decision,
            "message_ar": _message(item, event_type, old_decision, new_decision),
            "title": item.get("title"),
            "city": item.get("city"),
            "asking_price_nok": item.get("asking_price_nok"),
            "maximum_safe_bid_nok": item.get("maximum_safe_bid_nok"),
            "url": item.get("url"),
            "automatic_purchase": False,
            "automatic_bid": False,
        })
        sent_fingerprints.add(fingerprint)

    payload = {
        "generated_at": _now_iso(),
        "schema_version": 2,
        "alert_count": len(alerts),
        "alerts": alerts,
        "policy": {
            "new_strong_only": True,
            "decision_change_alerts": True,
            "deduplication": True,
            "automatic_purchase": False,
            "automatic_bid": False,
        },
    }
    return payload, current_state, sent_fingerprints
