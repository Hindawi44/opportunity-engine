#!/usr/bin/env python3
"""Synchronize canonical P4 decisions into dashboard and smart-alert outputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


DECISION_LABELS = {
    "BUY_REVIEW": "🟢 مراجعة للشراء",
    "WATCH": "🟡 مراقبة وجمع الأدلة",
    "REJECT": "🔴 رفض",
}


def load_object(path: Path) -> dict:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def decision_map(payload: dict) -> dict[str, dict]:
    decisions = payload.get("decisions", [])
    if not isinstance(decisions, list):
        return {}
    return {
        str(item.get("opportunity_id")): item
        for item in decisions
        if isinstance(item, dict) and item.get("opportunity_id")
    }


def sync_dashboard(payload: dict, decisions: dict[str, dict]) -> dict:
    result = dict(payload)
    for key in ("rows", "ranked", "items", "opportunities"):
        rows = result.get(key)
        if not isinstance(rows, list):
            continue
        updated = []
        for row in rows:
            if not isinstance(row, dict):
                updated.append(row)
                continue
            item = decisions.get(str(row.get("opportunity_id") or row.get("id") or ""))
            if not item:
                updated.append(row)
                continue
            decision = str(item["final_decision"])
            merged = dict(row)
            merged.update({
                "final_decision": decision,
                "final_decision_ar": item.get("final_decision_ar"),
                "decision": decision,
                "decision_label": DECISION_LABELS.get(decision, decision),
                "recommendation": decision,
                "recommendation_ar": item.get("final_decision_ar"),
                "maximum_purchase_price_nok": item.get("maximum_safe_bid_nok"),
                "maximum_safe_bid_nok": item.get("maximum_safe_bid_nok"),
                "decision_reasons_ar": item.get("decision_reasons_ar", []),
                "decision_warnings_ar": item.get("decision_warnings_ar", []),
                "next_actions_ar": item.get("next_actions_ar", []),
                "decision_source": "P4.1_final_decision",
            })
            updated.append(merged)
        result[key] = updated
    result["official_decision_field"] = "final_decision"
    result["decision_source"] = "data/decision_intelligence.json"
    return result


def sync_alerts(payload: dict, decisions: dict[str, dict]) -> dict:
    result = dict(payload)
    alerts = result.get("alerts", [])
    if not isinstance(alerts, list):
        alerts = []
    updated = []
    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        item = decisions.get(str(alert.get("opportunity_id") or ""))
        if not item:
            updated.append(alert)
            continue
        decision = str(item["final_decision"])
        # A rejected opportunity must never remain in the actionable alert outbox.
        if decision == "REJECT":
            continue
        merged = dict(alert)
        merged.update({
            "final_decision": decision,
            "final_decision_ar": item.get("final_decision_ar"),
            "recommendation": decision,
            "recommendation_ar": item.get("final_decision_ar"),
            "maximum_safe_bid_nok": item.get("maximum_safe_bid_nok"),
            "decision_reasons_ar": item.get("decision_reasons_ar", []),
            "decision_warnings_ar": item.get("decision_warnings_ar", []),
            "requires_human_approval": decision == "BUY_REVIEW",
            "decision_source": "P4.1_final_decision",
        })
        updated.append(merged)
    result["alerts"] = updated
    result["official_decision_field"] = "final_decision"
    result["decision_source"] = "data/decision_intelligence.json"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decisions", default="data/decision_intelligence.json")
    parser.add_argument("--dashboard", default="data/dashboard.json")
    parser.add_argument("--alerts", default="data/smart_alerts.json")
    args = parser.parse_args()

    decisions_payload = load_object(Path(args.decisions))
    decisions = decision_map(decisions_payload)
    dashboard_path = Path(args.dashboard)
    alerts_path = Path(args.alerts)
    save(dashboard_path, sync_dashboard(load_object(dashboard_path), decisions))
    save(alerts_path, sync_alerts(load_object(alerts_path), decisions))
    print(json.dumps({"decision_count": len(decisions), "dashboard": str(dashboard_path), "alerts": str(alerts_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
