"""Persistent review queue and duplicate-safe alert generation for V3.5."""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Iterable

READY_GATE = "READY_FOR_FINANCIAL_REVIEW"
VALID_QUEUE_STATUSES = {"PENDING_REVIEW", "SNOOZED", "IGNORED", "REVIEWED"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def alert_fingerprint(candidate: dict[str, Any]) -> str:
    fields = (
        candidate.get("opportunity_id"),
        candidate.get("decision_gate"),
        candidate.get("expected_profit"),
        candidate.get("roi"),
        candidate.get("verified_comparable_count"),
        candidate.get("verified_cost_component_count"),
        candidate.get("evidence_version"),
    )
    return sha256("|".join(_text(value) for value in fields).encode("utf-8")).hexdigest()


def _eligible(candidate: dict[str, Any]) -> bool:
    return bool(
        _text(candidate.get("opportunity_id"))
        and candidate.get("decision_gate") == READY_GATE
        and candidate.get("automatic_purchase_decision") is False
        and int(candidate.get("verified_comparable_count") or 0) >= 3
        and int(candidate.get("verified_cost_component_count") or 0) >= 6
        and _number(candidate.get("expected_profit")) is not None
        and _number(candidate.get("roi")) is not None
    )


def _priority(candidate: dict[str, Any]) -> str:
    roi = _number(candidate.get("roi")) or 0.0
    profit = _number(candidate.get("expected_profit")) or 0.0
    if roi >= 50 and profit >= 10000:
        return "HIGH"
    if roi >= 25:
        return "MEDIUM"
    return "NORMAL"


def normalize_review_state(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    return {
        "schema_version": "3.5",
        "items": dict(payload.get("items") or {}) if isinstance(payload.get("items"), dict) else {},
        "alert_fingerprints": sorted({str(x) for x in (payload.get("alert_fingerprints") or [])}),
    }


def update_review_queue(
    candidates: Iterable[dict[str, Any]],
    state_payload: dict[str, Any] | None = None,
    *,
    run_at: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate_list = [item for item in candidates if isinstance(item, dict)]
    state = normalize_review_state(state_payload)
    seen_alerts = set(state["alert_fingerprints"])
    alerts: list[dict[str, Any]] = []
    ignored: list[str] = []

    for candidate in candidate_list:
        opportunity_id = _text(candidate.get("opportunity_id"))
        if not _eligible(candidate):
            if opportunity_id:
                ignored.append(opportunity_id)
            continue

        fingerprint = alert_fingerprint(candidate)
        existing = dict(state["items"].get(opportunity_id) or {})
        previous_fingerprint = existing.get("last_alert_fingerprint")
        should_alert = fingerprint != previous_fingerprint and fingerprint not in seen_alerts
        reason = "NEWLY_ELIGIBLE" if not existing else "MATERIAL_UPDATE"

        item = {
            "opportunity_id": opportunity_id,
            "decision_gate": READY_GATE,
            "priority": _priority(candidate),
            "queue_status": existing.get("queue_status") if existing.get("queue_status") in VALID_QUEUE_STATUSES else "PENDING_REVIEW",
            "queued_at": existing.get("queued_at") or run_at,
            "updated_at": run_at,
            "last_alert_at": run_at if should_alert else existing.get("last_alert_at"),
            "last_alert_fingerprint": fingerprint if should_alert else previous_fingerprint,
            "expected_profit": candidate.get("expected_profit"),
            "roi": candidate.get("roi"),
            "verified_comparable_count": candidate.get("verified_comparable_count"),
            "verified_cost_component_count": candidate.get("verified_cost_component_count"),
            "automatic_purchase_decision": False,
        }
        state["items"][opportunity_id] = item

        if should_alert:
            seen_alerts.add(fingerprint)
            alerts.append({
                "opportunity_id": opportunity_id,
                "reason": reason,
                "priority": item["priority"],
                "fingerprint": fingerprint,
                "created_at": run_at,
            })

    state["alert_fingerprints"] = sorted(seen_alerts)
    queue = sorted(
        state["items"].values(),
        key=lambda item: (
            {"HIGH": 0, "MEDIUM": 1, "NORMAL": 2}.get(item.get("priority"), 3),
            -float(item.get("roi") or 0),
            -float(item.get("expected_profit") or 0),
            str(item.get("opportunity_id")),
        ),
    )
    report = {
        "schema_version": "3.5",
        "run_at": run_at,
        "candidates_received": len(candidate_list),
        "review_queue_created": True,
        "review_queue_count": len(queue),
        "new_alerts_count": len(alerts),
        "duplicate_alerts": 0,
        "alerts": alerts,
        "queue": queue,
        "ignored_ineligible": ignored,
        "automatic_purchase_decision": False,
        "errors": [],
        "status": "PASS",
    }
    return report, state


def set_queue_status(
    state_payload: dict[str, Any], opportunity_id: str, status: str, *, changed_at: str
) -> dict[str, Any]:
    if status not in VALID_QUEUE_STATUSES:
        raise ValueError(f"unsupported queue status: {status}")
    state = normalize_review_state(state_payload)
    if opportunity_id not in state["items"]:
        raise KeyError(opportunity_id)
    state["items"][opportunity_id]["queue_status"] = status
    state["items"][opportunity_id]["updated_at"] = changed_at
    return state
