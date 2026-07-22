#!/usr/bin/env python3
"""Track completion of the fixed source-expansion phase."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _read(path: str) -> dict[str, object]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def build_status(plan: dict[str, object], funnel: dict[str, object]) -> dict[str, object]:
    funnel_rows = funnel.get("sources", [])
    funnel_by_source = {
        str(row.get("source")): row
        for row in funnel_rows
        if isinstance(row, dict) and row.get("source")
    } if isinstance(funnel_rows, list) else {}

    rows: list[dict[str, object]] = []
    markets = plan.get("markets", [])
    if not isinstance(markets, list):
        markets = []
    for market in markets:
        if not isinstance(market, dict):
            continue
        market_name = str(market.get("market") or "").strip()
        sources = market.get("sources", [])
        if not isinstance(sources, list):
            continue
        for source in sources:
            if not isinstance(source, dict):
                continue
            name = str(source.get("source") or "").strip()
            if not name:
                continue
            observed = funnel_by_source.get(name, {})
            status = str(observed.get("status") or source.get("current_status") or "planned")
            fetched = int(observed.get("fetched", 0) or 0)
            error = observed.get("error")
            complete = status == "collecting" and fetched > 0 and not error
            blocked = status == "awaiting_authorized_configuration"
            rows.append({
                "market": market_name,
                "source": name,
                "priority": source.get("priority"),
                "status": status,
                "fetched": fetched,
                "complete": complete,
                "blocked_by_authorized_access": blocked,
                "error": error,
            })

    required = len(rows)
    complete_count = sum(bool(row["complete"]) for row in rows)
    blocked_count = sum(bool(row["blocked_by_authorized_access"]) for row in rows)
    planned_count = sum(row["status"] == "planned" for row in rows)
    phase_complete = required > 0 and complete_count == required
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": plan.get("phase"),
        "phase_complete": phase_complete,
        "economic_ranking_unlocked": phase_complete,
        "summary": {
            "required_source_count": required,
            "complete_source_count": complete_count,
            "blocked_source_count": blocked_count,
            "planned_source_count": planned_count,
            "remaining_source_count": required - complete_count,
        },
        "sources": rows,
        "completion_rule": plan.get("completion_rule"),
    }


def main() -> int:
    plan = _read("config/source_expansion_plan.json")
    funnel = _read("data/source_funnel.json")
    payload = build_status(plan, funnel)
    output = Path("data/source_expansion_status.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), **payload["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
