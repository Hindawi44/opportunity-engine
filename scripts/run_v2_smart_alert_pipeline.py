from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.smart_alert_engine import build_smart_alerts

DATA = Path("data")
DECISIONS = DATA / "decision_intelligence.json"
ALERTS = DATA / "smart_alerts_v2.json"
STATE = DATA / "smart_alert_state.json"
HISTORY = DATA / "smart_alert_history.json"


def _load(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def main() -> int:
    decision_payload = _load(DECISIONS, {})
    decisions = decision_payload.get("decisions", [])
    if not isinstance(decisions, list):
        raise ValueError("decision_intelligence.json must contain a decisions list")

    state_payload = _load(STATE, {"decisions_by_id": {}})
    history_payload = _load(HISTORY, {"sent_fingerprints": [], "events": []})
    previous_state = state_payload.get("decisions_by_id", {})
    sent = set(history_payload.get("sent_fingerprints", []))

    alerts, current_state, updated_sent = build_smart_alerts(decisions, previous_state, sent)
    events = list(history_payload.get("events", [])) + list(alerts["alerts"])

    _write(ALERTS, alerts)
    _write(STATE, {"schema_version": 1, "decisions_by_id": current_state})
    _write(HISTORY, {
        "schema_version": 1,
        "sent_fingerprints": sorted(updated_sent),
        "event_count": len(events),
        "events": events,
    })
    print(f"Generated {alerts['alert_count']} smart alerts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
