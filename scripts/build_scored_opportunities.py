#!/usr/bin/env python3
"""Build one transparent, evidence-gated score and recommendation per opportunity.

The engine never converts missing evidence into a positive financial assumption. A
high operational score may promote an item to MONITOR, but BUY_REVIEW is only
possible when the upstream economic evaluation contains complete verified inputs,
positive profit, and a sufficient ROI. Final purchase approval remains human.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _text(item: dict[str, object]) -> str:
    return re.sub(
        r"\s+",
        " ",
        f"{item.get('title') or ''} {item.get('description') or ''}".casefold(),
    )


def _economics(evaluation: dict[str, object]) -> tuple[float, list[str]]:
    profit = _number(evaluation.get("expected_profit_nok"))
    roi = _number(evaluation.get("roi_percent"))
    reasons: list[str] = []
    if evaluation.get("decision") != "REVIEW_NUMBERS" or profit is None or roi is None:
        return 0.0, ["verified_economics:0/35"]

    roi_points = max(0.0, min(roi / 50.0, 1.0)) * 20.0
    profit_points = max(0.0, min(profit / 20_000.0, 1.0)) * 15.0
    total = roi_points + profit_points
    reasons.append(f"verified_roi:{roi_points:.1f}/20")
    reasons.append(f"verified_profit:{profit_points:.1f}/15")
    return total, reasons


def _evidence(evaluation: dict[str, object]) -> tuple[float, list[str]]:
    missing = evaluation.get("missing_evidence")
    missing_count = len(missing) if isinstance(missing, list) else 0
    comparables = evaluation.get("evidence")
    comparables = comparables.get("market_comparables_nok") if isinstance(comparables, dict) else []
    comparable_count = len(comparables) if isinstance(comparables, list) else 0

    completeness = max(0.0, 15.0 - min(15.0, missing_count * 2.0))
    comparable_points = min(10.0, comparable_count / 3.0 * 10.0)
    return completeness + comparable_points, [
        f"evidence_completeness:{completeness:.1f}/15",
        f"verified_comparables:{comparable_points:.1f}/10",
    ]


def _marketability(item: dict[str, object]) -> tuple[float, list[str]]:
    text = _text(item)
    easy = (
        "kontorstol", "kontormøbel", "butikkinnredning", "hylle", "verktøy",
        "symaskin", "møbel", "lampe", "skjerm", "bord", "stol", "varelager",
    )
    difficult = (
        "spesialbygget", "komplett fabrikk", "produksjonslinje", "defekt",
        "ukjent stand", "reservedeler", "tungmaskin",
    )
    score = 7.0
    if any(word in text for word in easy):
        score += 6.0
    if any(word in text for word in difficult):
        score -= 7.0
    if _number(item.get("asking_price_nok")) is not None:
        score += 2.0
    score = max(0.0, min(score, 15.0))
    return score, [f"marketability:{score:.1f}/15"]


def _logistics(item: dict[str, object]) -> tuple[float, list[str]]:
    text = _text(item)
    hard = (
        "demontering", "må demonteres", "truck nødvendig", "kran nødvendig",
        "hentes med lastebil", "produksjonslinje", "tung",
    )
    easy = ("kan sendes", "pakkes", "pall", "lett", "demontert")
    score = 6.0
    if any(word in text for word in hard):
        score -= 6.0
    if any(word in text for word in easy):
        score += 3.0
    if item.get("city"):
        score += 1.0
    score = max(0.0, min(score, 10.0))
    return score, [f"logistics:{score:.1f}/10"]


def _listing_quality(item: dict[str, object]) -> tuple[float, list[str]]:
    relevance = _number(item.get("relevance_score")) or 0.0
    relevance_points = max(0.0, min(relevance / 100.0 * 7.0, 7.0))
    price_points = 3.0 if _number(item.get("asking_price_nok")) is not None else 0.0
    location_points = 2.0 if item.get("city") else 0.0
    deadline_points = 2.0 if item.get("ends_at") else 0.0
    source_points = 1.0 if item.get("source") or item.get("source_name") else 0.0
    total = relevance_points + price_points + location_points + deadline_points + source_points
    return total, [
        f"relevance:{relevance_points:.1f}/7",
        f"listing_fields:{price_points + location_points + deadline_points + source_points:.1f}/8",
    ]


def score_opportunity(
    item: dict[str, object], evaluation: dict[str, object] | None
) -> dict[str, object]:
    evaluation = evaluation or {}
    economics, economics_reasons = _economics(evaluation)
    evidence, evidence_reasons = _evidence(evaluation)
    marketability, marketability_reasons = _marketability(item)
    logistics, logistics_reasons = _logistics(item)
    quality, quality_reasons = _listing_quality(item)

    raw = economics + evidence + marketability + logistics + quality
    upstream_decision = str(evaluation.get("decision") or "EVIDENCE_REQUIRED")
    profit = _number(evaluation.get("expected_profit_nok"))
    roi = _number(evaluation.get("roi_percent"))

    # Evidence gates are hard caps. They prevent attractive-looking listings from
    # becoming buy candidates before economics are complete and verified.
    if upstream_decision != "REVIEW_NUMBERS":
        raw = min(raw, 59.0)
    elif profit is None or roi is None or profit <= 0:
        raw = min(raw, 29.0)
    elif roi < 15.0:
        raw = min(raw, 49.0)

    total = round(max(0.0, min(raw, 100.0)), 2)
    if (
        upstream_decision == "REVIEW_NUMBERS"
        and profit is not None
        and roi is not None
        and profit >= 2_000.0
        and roi >= 30.0
        and total >= 75.0
    ):
        recommendation = "BUY_REVIEW"
        recommendation_ar = "مراجعة للشراء"
    elif total >= 45.0:
        recommendation = "MONITOR"
        recommendation_ar = "مراقبة"
    else:
        recommendation = "REJECT"
        recommendation_ar = "رفض"

    grade = "A" if total >= 80 else "B" if total >= 65 else "C" if total >= 50 else "D" if total >= 35 else "E"
    merged = dict(item)
    for key in (
        "decision", "total_cost_nok", "conservative_resale_value_nok",
        "expected_profit_nok", "roi_percent", "maximum_safe_bid_nok",
        "missing_evidence",
    ):
        merged[key] = evaluation.get(key)
    merged.update(
        {
            "opportunity_score": total,
            "score_grade": grade,
            "recommendation": recommendation,
            "recommendation_ar": recommendation_ar,
            "requires_human_approval": recommendation == "BUY_REVIEW",
            "score_components": {
                "verified_economics": round(economics, 2),
                "evidence": round(evidence, 2),
                "marketability": round(marketability, 2),
                "logistics": round(logistics, 2),
                "listing_quality": round(quality, 2),
            },
            "score_reasons": [
                *economics_reasons,
                *evidence_reasons,
                *marketability_reasons,
                *logistics_reasons,
                *quality_reasons,
                f"evidence_gate:{upstream_decision}",
            ],
        }
    )
    return merged


def _append_history(path: Path, generated_at: str, opportunities: list[dict[str, object]]) -> None:
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = {"schema_version": 1, "runs": []}
    runs = payload.get("runs")
    if not isinstance(runs, list):
        runs = []
    snapshot = {
        "generated_at": generated_at,
        "candidate_count": len(opportunities),
        "buy_review_count": sum(item["recommendation"] == "BUY_REVIEW" for item in opportunities),
        "monitor_count": sum(item["recommendation"] == "MONITOR" for item in opportunities),
        "reject_count": sum(item["recommendation"] == "REJECT" for item in opportunities),
        "scores": [
            {
                "opportunity_id": item.get("opportunity_id"),
                "score": item.get("opportunity_score"),
                "recommendation": item.get("recommendation"),
            }
            for item in opportunities
        ],
    }
    runs.append(snapshot)
    payload["runs"] = runs[-90:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default="data/opportunity_review_queue.json")
    parser.add_argument("--evaluations", default="data/economic_evaluation_queue.json")
    parser.add_argument("--output", default="data/scored_opportunities.json")
    parser.add_argument("--history", default="data/scoring_history.json")
    args = parser.parse_args()

    queue_payload = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    queue = queue_payload.get("queue", [])
    if not isinstance(queue, list):
        raise ValueError("review queue must be a list")

    evaluation_path = Path(args.evaluations)
    evaluation_payload: dict[str, Any] = (
        json.loads(evaluation_path.read_text(encoding="utf-8")) if evaluation_path.exists() else {}
    )
    evaluations = evaluation_payload.get("evaluations", [])
    by_id = {
        str(item.get("opportunity_id")): item
        for item in evaluations
        if isinstance(item, dict) and item.get("opportunity_id")
    } if isinstance(evaluations, list) else {}

    scored = [
        score_opportunity(item, by_id.get(str(item.get("opportunity_id"))))
        for item in queue
        if isinstance(item, dict)
    ]
    scored.sort(
        key=lambda item: (
            -float(item["opportunity_score"]),
            int(item.get("priority") or 99),
            str(item.get("title") or ""),
        )
    )
    generated_at = datetime.now(timezone.utc).isoformat()
    actionable = [item for item in scored if item["recommendation"] != "REJECT"]
    payload = {
        "schema_version": 1,
        "generated_at": generated_at,
        "method": "transparent evidence-gated unified scoring; BUY_REVIEW always requires human approval",
        "candidate_count": len(scored),
        "actionable_count": len(actionable),
        "buy_review_count": sum(item["recommendation"] == "BUY_REVIEW" for item in scored),
        "monitor_count": sum(item["recommendation"] == "MONITOR" for item in scored),
        "reject_count": sum(item["recommendation"] == "REJECT" for item in scored),
        "opportunities": scored,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _append_history(Path(args.history), generated_at, scored)
    print(json.dumps({"candidate_count": len(scored), "actionable_count": len(actionable), "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
