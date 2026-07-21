#!/usr/bin/env python3
"""Build a conservative manual-review queue from the daily snapshot.

Clearly unsuitable categories are excluded. Strong target-category matches are
preferred. When none exist, fallback may keep only weak matches that still belong
to an explicit target category. Unrelated listings never enter the queue.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

TARGET_TERMS = {
    # Shop fittings and retail display
    "butikkinnredning": 24, "butikk inventar": 22, "butikkinventar": 22,
    "butikkhylle": 18, "butikkreol": 18, "butikkstativ": 18,
    "prøverom": 20, "klesstativ": 18, "mannekeng": 18,
    "utstillingsdukke": 18, "prøvedukke": 18,
    "utstillingsstativ": 16, "displaystativ": 16, "varedisplay": 16,
    "salgsdisk": 16, "butikkdisk": 16, "kassadisk": 16,
    "resepsjonsdisk": 15, "vitrineskap": 14, "glassmonter": 14,

    # Warehouse, shelving and easy-to-resell business equipment
    "varelager": 18, "lagerinnredning": 18, "lagerutstyr": 15,
    "lagerreol": 15, "pallereol": 15, "reolsystem": 15,
    "stålreol": 14, "hyllereol": 14, "reol": 9, "hylle": 8,
    "arbeidsbord": 13, "arbeidsbenk": 13, "pakkebord": 14,
    "verkstedbenk": 12, "materialskap": 12, "stålskap": 12, "skap": 7,

    # Office and commercial furniture
    "kontormøbler": 17, "kontorinnredning": 17,
    "skrivebord": 13, "kontorpult": 13, "kontorstol": 13,
    "møtebord": 13, "konferansebord": 13, "arkivskap": 13,
    "garderobeskap": 12, "resepsjonsmøbler": 14,

    # Textile, clothing and sewing opportunities
    "tekstil": 16, "stoffparti": 18, "metervare": 16,
    "klær": 16, "klesparti": 18, "brudekjole": 18,
    "symaskin": 18, "industrisymaskin": 22, "overlock": 19,
    "systue": 18, "syutstyr": 16,
}

EXCLUDE_TERMS = {
    "varebil": "vehicle", "lastebil": "heavy_vehicle", "personbil": "vehicle",
    "traktor": "heavy_equipment", "gravemaskin": "heavy_equipment",
    "hjullaster": "heavy_equipment", "tilhenger": "vehicle_equipment",
    "båt": "vehicle", "jetski": "vehicle", "motorsykkel": "vehicle",
    "generator": "complex_technical", "kompressor": "complex_technical",
    "sveis": "complex_technical", "industrirobot": "complex_technical",
    "gassmåler": "specialized_technical", "øyedusj": "specialized_technical",
    "dørhåndtak": "low_relevance_goods", "lamper": "low_relevance_goods",
    "ledrør": "low_relevance_goods", "servantbatteri": "plumbing_goods",
    "kjøkkenbatteri": "plumbing_goods", "blandebatteri": "plumbing_goods",
    "kran": "plumbing_goods", "armatur": "plumbing_goods",
    "toalett": "sanitary_goods", "dusj": "sanitary_goods",
    "water conditioner": "specialized_technical", "vannbehandler": "specialized_technical",
    "magnetic water": "specialized_technical", "batteri": "low_relevance_goods",
}

URL_CATEGORY_EXCLUSIONS = {
    "/auksjon/bruktbil/": "vehicle",
    "/auksjon/lastebil_og_henger/": "heavy_vehicle",
    "/auksjon/landbruk/": "heavy_equipment",
    "/auksjon/anlegg/": "heavy_equipment",
    "/auksjon/bat/": "vehicle",
    "/auksjon/båt/": "vehicle",
    "/auksjon/motorsykkel/": "vehicle",
}

GENERIC_ONLY_TERMS = {
    "parti", "overskudd", "overskuddsmateriell", "forskjellig",
    "diverse", "ingen minstepris",
}
GENERIC_PENALTIES = {
    "kabel": 10, "reservedel": 9, "verktøy": 6,
    "elektronikk": 6, "monteringsutstyr": 6,
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def classify(row: dict[str, object]) -> dict[str, object]:
    title = str(row.get("title") or "")
    normalized = normalize(title)
    url = str(row.get("url") or "")
    normalized_url = url.casefold()
    reasons: list[str] = []
    exclusions: list[str] = []
    score = 0
    matched_targets: list[str] = []

    for term, reason in EXCLUDE_TERMS.items():
        if term in normalized:
            exclusions.append(reason)

    for path, reason in URL_CATEGORY_EXCLUSIONS.items():
        if path in normalized_url:
            exclusions.append(reason)
            reasons.append(f"excluded_url_category:{path}")

    for term, points in TARGET_TERMS.items():
        if term in normalized:
            matched_targets.append(term)
            score += points
            reasons.append(f"target:{term}+{points}")

    for term, penalty in GENERIC_PENALTIES.items():
        if term in normalized:
            score -= penalty
            reasons.append(f"generic:{term}-{penalty}")

    generic_matches = sorted(term for term in GENERIC_ONLY_TERMS if term in normalized)
    if generic_matches and not matched_targets:
        exclusions.append("generic_unspecified_lot")
        reasons.append("generic lot without a concrete target category")

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
        status, priority = "excluded", 0
    elif score >= 22:
        status, priority = "review_first", 1
    elif score >= 12:
        status, priority = "review_if_capacity", 2
    else:
        status, priority = "low_relevance", 3

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
        "matched_target_terms": matched_targets,
        "exclusion_reasons": sorted(set(exclusions)),
        "evidence_needed": [
            "three_verified_market_comparables", "auction_fee", "vat_status",
            "transport_cost", "dismantling_cost", "condition_and_missing_parts",
        ],
        "market_search_query": re.sub(
            r"\s+(\d+\s+bud|\d+t\s+\d+m.*)$", "", title, flags=re.IGNORECASE
        ).strip(),
    }


def _fallback_items(low_relevance: list[dict[str, object]], count: int) -> list[dict[str, object]]:
    candidates = [item for item in low_relevance if item.get("matched_target_terms")]
    candidates.sort(key=lambda item: (-int(item["relevance_score"]), str(item["title"])))
    selected: list[dict[str, object]] = []
    for original in candidates[: max(count, 0)]:
        item = dict(original)
        item["status"] = "discovery_fallback"
        item["priority"] = 3
        item["reasons"] = [*list(item["reasons"]), "fallback:weak_target_category_candidate"]
        selected.append(item)
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a conservative opportunity review queue")
    parser.add_argument("--snapshot", default="data/todays_opportunities.json")
    parser.add_argument("--output", default="data/opportunity_review_queue.json")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--fallback-limit", type=int, default=3)
    args = parser.parse_args()

    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    rows = snapshot.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError("snapshot rows must be a list")

    classified = [classify(row) for row in rows if isinstance(row, dict)]
    included = [item for item in classified if item["status"] in {"review_first", "review_if_capacity"}]
    included.sort(key=lambda item: (item["priority"], -item["relevance_score"], str(item["title"])))
    excluded = [item for item in classified if item["status"] == "excluded"]
    low_relevance = [item for item in classified if item["status"] == "low_relevance"]

    selected = included[: max(args.limit, 1)]
    fallback_used = False
    if not selected and low_relevance:
        selected = _fallback_items(low_relevance, min(args.fallback_limit, max(args.limit, 1)))
        fallback_used = bool(selected)

    payload = {
        "schema_version": 6,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_snapshot": args.snapshot,
        "method": "expanded practical target categories with strict vehicle, heavy-equipment and unrelated-item exclusions; no financial values are invented",
        "input_count": len(classified),
        "selected_count": len(selected),
        "excluded_count": len(excluded),
        "low_relevance_omitted_count": len(low_relevance) - (len(selected) if fallback_used else 0),
        "fallback_used": fallback_used,
        "fallback_count": len(selected) if fallback_used else 0,
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
    print(json.dumps({
        "input_count": len(classified), "selected_count": len(selected),
        "excluded_count": len(excluded), "fallback_used": fallback_used,
        "output": str(output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
