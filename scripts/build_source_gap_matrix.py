#!/usr/bin/env python3
"""Build the official source coverage gap matrix."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ALLOWED = {"ACTIVE", "CODE_READY", "BLOCKED_AUTH", "PLANNED", "DEPRECATED"}


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def flatten_plan(plan: dict) -> list[dict]:
    rows: list[dict] = []
    for market in plan.get("markets", []):
        if not isinstance(market, dict):
            continue
        for source in market.get("sources", []):
            if isinstance(source, dict):
                rows.append({**source, "market": market.get("market")})
    return rows


def classify(planned: dict, actual: dict | None) -> str:
    declared = str(planned.get("audit_status") or "PLANNED").upper()
    if actual:
        if actual.get("active") and actual.get("configured") and not actual.get("error"):
            return "ACTIVE"
        if actual.get("required_configuration"):
            return "BLOCKED_AUTH"
        if actual.get("configured") and not actual.get("active"):
            return "CODE_READY"
    return declared if declared in ALLOWED else "PLANNED"


def build_matrix(plan: dict, funnel: dict, generated_at: str) -> dict:
    actual_by_name = {
        str(item.get("source")): item
        for item in funnel.get("sources", [])
        if isinstance(item, dict) and item.get("source")
    }
    rows = []
    counts = {status: 0 for status in sorted(ALLOWED)}
    for planned in flatten_plan(plan):
        name = str(planned.get("source"))
        actual = actual_by_name.get(name)
        status = classify(planned, actual)
        counts[status] += 1
        rows.append({
            "source": name,
            "market": planned.get("market"),
            "priority": planned.get("priority"),
            "status": status,
            "fetched": int((actual or {}).get("fetched") or 0),
            "error": (actual or {}).get("error"),
            "required_configuration": (actual or {}).get("required_configuration", []),
            "access_mode": (actual or {}).get("access_mode"),
            "channel": planned.get("channel"),
        })
    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "allowed_statuses": sorted(ALLOWED),
        "source_count": len(rows),
        "status_counts": counts,
        "sources": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", default="config/source_expansion_plan.json")
    parser.add_argument("--source-funnel", default="data/source_funnel.json")
    parser.add_argument("--output", default="data/source_gap_matrix.json")
    args = parser.parse_args()
    payload = build_matrix(
        load(Path(args.plan)),
        load(Path(args.source_funnel)),
        datetime.now(timezone.utc).isoformat(),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "status_counts": payload["status_counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
