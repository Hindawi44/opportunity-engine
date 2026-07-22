#!/usr/bin/env python3
"""Append the strongest P2-scored opportunities to the persistent alert outbox."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _signature(item: dict[str, object]) -> str:
    value = "|".join(
        str(part)
        for part in (
            item.get("opportunity_id"),
            item.get("recommendation"),
            item.get("opportunity_score"),
            item.get("asking_price_nok"),
        )
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scored", default="data/scored_opportunities.json")
    parser.add_argument("--alerts", default="data/smart_alerts.json")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    scored = json.loads(Path(args.scored).read_text(encoding="utf-8"))
    opportunities = scored.get("opportunities", [])
    if not isinstance(opportunities, list):
        raise ValueError("scored opportunities must be a list")

    alerts_path = Path(args.alerts)
    if alerts_path.exists():
        state = json.loads(alerts_path.read_text(encoding="utf-8"))
    else:
        state = {"schema_version": 1, "signatures": [], "alerts": []}
    if not isinstance(state, dict) or not isinstance(state.get("alerts"), list):
        raise ValueError("invalid smart alerts database")
    signatures = set(state.get("signatures") or [])

    candidates = [
        item for item in opportunities
        if isinstance(item, dict)
        and item.get("recommendation") in {"BUY_REVIEW", "MONITOR"}
        and float(item.get("opportunity_score") or 0) >= 45.0
    ][: max(1, args.limit)]

    created: list[dict[str, object]] = []
    for item in candidates:
        signature = _signature(item)
        if signature in signatures:
            continue
        signatures.add(signature)
        recommendation = str(item.get("recommendation"))
        created.append(
            {
                "alert_id": signature,
                "opportunity_id": item.get("opportunity_id"),
                "alert_type": "p2_buy_review" if recommendation == "BUY_REVIEW" else "p2_monitor",
                "severity": "critical" if recommendation == "BUY_REVIEW" else "medium",
                "title": item.get("title") or item.get("opportunity_id"),
                "url": item.get("url"),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "opportunity_score": item.get("opportunity_score"),
                "score_grade": item.get("score_grade"),
                "recommendation": recommendation,
                "recommendation_ar": item.get("recommendation_ar"),
                "expected_profit_nok": item.get("expected_profit_nok"),
                "roi_percent": item.get("roi_percent"),
                "requires_human_approval": item.get("requires_human_approval", False),
                "summary": "مراجعة بشرية مطلوبة قبل أي شراء" if recommendation == "BUY_REVIEW" else "فرصة تستحق المراقبة وجمع الأدلة الناقصة",
            }
        )

    state["schema_version"] = max(2, int(state.get("schema_version") or 1))
    state["signatures"] = sorted(signatures)
    state["alerts"].extend(created)
    state["last_scoring_run"] = scored.get("generated_at")
    state["last_scoring_alert_count"] = len(created)
    alerts_path.parent.mkdir(parents=True, exist_ok=True)
    alerts_path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"created_alert_count": len(created), "alerts": str(alerts_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
