#!/usr/bin/env python3
"""Build a conservative manual-review queue from the daily opportunity snapshot.

This stage does not invent resale values or operating costs. It only removes
clearly unsuitable categories and ranks the remaining listings for evidence
collection (market comparables, transport, VAT, fees, and condition).
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

TARGET_TERMS = {
    "butikkinnredning": 18,
    "butikk": 10,
    "inventar": 14,
    "innredning": 12,
    "reol": 10,
    "hylle": 9,
    "disk": 9,
    "prøverom": 15,
    "klesstativ": 14,
    "stativ": 6,
    "kontormøbler": 14,
    "kontor": 8,
    "skrivebord": 10,
    "kontorstol": 10,
    "skap": 7,
    "bord": 6,
    "stol": 5,
    "lager": 7,
    "varelager": 15,
    "parti": 8,
    "overskudd": 12,
    "tekstil": 13,
    "klær": 13,
    "kjole": 10,
    "brudekjole": 16,
    "symaskin": 15,
    "industrisymaskin": 18,
    "mannekeng": 12,
    "utstillings": 8,
}

EXCLUDE_TERMS = {
    "bil": "vehicle",
    "varebil": "vehicle",
    "lastebil": "heavy_vehicle",
    "traktor": "heavy_equipment",
    "gravemaskin": "heavy_equipment",
    "hjullaster": "heavy_equipment",
    "tilhenger": "vehicle_equipment",
    "båt": "vehicle",
    "motorsykkel": "vehicle",
    "motor": "complex_mechanical",
    "generator": "complex_technical",
    "kompressor": "complex_technical",
    "sveis": "complex_technical",
    "industrirobot": "complex_technical",
}

GENERIC_PENALTIES = {
    "kabel": 8,
    "reservedel": 7,
    "batteri": 5,
    "verktøy": 4,
    "elektronikk": 4,
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def classify(row: dict[str, object]) -> dict[str, object]:
    title = str(row.get("title") or "")
    normalized = normalize(title)
    reasons: list[str] = []
    exclusions: list[str] = []
    score = 0

    for term, reason in EXCLUDE_TERMS.items():
        if re.search(rf"\b{re.escape(term)}\w*", normalized):
            exclusions.append(reason)

    for term, points in TARGET_TERMS.items():
        if term in normalized:
            score += points
            reasons.append(f"target:{term}+{points}")

    for term, penalty in GENERIC_PENALTIES.items():
        if term in normalized:
            score -= penalty
            reasons.append(f"generic:{term}-{penalty}")

    asking_price = row.get("asking_price_nok")
    if isinstance(asking_price, (int, float)) and asking_price > 0:
        score += 5
        reasons.append("asking_price_present+5")
    else:
        reasons.append("asking_price_missing")

    if row.get("city"):
        score += 3
        reasons.append("location_present+3")
    if row.get("ends_at"):
        score += 3
        reasons.append("end_time_present+3")

    if exclusions:
        status = "excluded"
        priority = 0
    elif score >= 20:
        status = "review_first"
        priority = 1
    elif score >= 8:
        status = "review_if_capacity"
        priority = 2
    else:
        status = "low_relevance"
        priority = 3

    return {
        "opportunity_id": row.get("opportunity_id"),
        "title": title,
        "url": row.get("url"),
        "asking_price_nok": asking_price,
        "city": row.get("city"),
        "ends_at": row.get("ends_at"),
        "status": status,
        "priority": priority,
        "relevance_score": max(score, 0),
        "reasons": reasons,
        "exclusion_reasons": sorted(set(exclusions)),
        "evidence_needed": [
            "three_verified_market_comparables",
            "auction_fee",
            "vat_status",
            "transport_cost",
            "dismantling_cost",
            "condition_and_missing_parts",
        ],
        "market_search_query": re.sub(r"\s+(\d+\s+bud|\d+t\s+\d+m.*)$", "", title, flags=re.IGNORECASE).strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a conservative opportunity review queue")
    parser.add_argument("--snapshot", default="data/todays_opportunities.json")
    parser.add_argument("--output", default="data/opportunity_review_queue.json")
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()

    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    rows = snapshot.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError("snapshot rows must be a list")

    classified = [classify(row) for row in rows if isinstance(row, dict)]
    included = [item for item in classified if item["status"] != "excluded"]
    included.sort(key=lambda item: (item["priority"], -item["relevance_score"], str(item["title"])))
    excluded = [item for item in classified if item["status"] == "excluded"]

    selected = included[: max(args.limit, 1)]
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_snapshot": args.snapshot,
        "method": "keyword relevance and explicit exclusion rules; no resale values or costs are invented",
        "input_count": len(classified),
        "selected_count": len(selected),
        "excluded_count": len(excluded),
        "review_first_count": sum(item["status"] == "review_first" for item in selected),
        "queue": selected,
        "excluded_summary": {
            reason: sum(reason in item["exclusion_reasons"] for item in excluded)
            for reason in sorted({reason for item in excluded for reason in item["exclusion_reasons"]})
        },
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"input_count": len(classified), "selected_count": len(selected), "excluded_count": len(excluded), "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
