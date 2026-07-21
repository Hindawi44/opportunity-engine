#!/usr/bin/env python3
"""Build a concise top-five opportunity report without inventing economics."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _score(item: dict[str, object]) -> tuple[int, list[str]]:
    """Return a transparent 0-100 operational score and its reasons.

    Relevance and evidence completeness are scored. Profit and ROI contribute only
    when they were calculated from verified evidence upstream.
    """
    score = 0
    reasons: list[str] = []

    relevance = _number(item.get("relevance_score")) or 0.0
    relevance_points = min(35, max(0, round(relevance)))
    score += relevance_points
    reasons.append(f"relevance:{relevance_points}/35")

    priority = item.get("priority")
    priority_points = {1: 15, 2: 9, 3: 4}.get(priority, 0)
    score += priority_points
    reasons.append(f"priority:{priority_points}/15")

    if _number(item.get("asking_price_nok")) is not None:
        score += 5
        reasons.append("asking_price:5/5")
    else:
        reasons.append("asking_price:0/5")

    if item.get("city"):
        score += 5
        reasons.append("location:5/5")
    else:
        reasons.append("location:0/5")

    if item.get("ends_at"):
        score += 5
        reasons.append("deadline:5/5")
    else:
        reasons.append("deadline:0/5")

    missing = item.get("missing_evidence")
    missing_count = len(missing) if isinstance(missing, list) else 0
    evidence_points = max(0, 20 - min(20, missing_count * 3))
    score += evidence_points
    reasons.append(f"evidence:{evidence_points}/20")

    profit = _number(item.get("expected_profit_nok"))
    roi = _number(item.get("roi_percent"))
    if profit is not None and roi is not None:
        economics_points = 15 if profit > 0 and roi >= 30 else 10 if profit > 0 and roi >= 15 else 4 if profit > 0 else 0
        score += economics_points
        reasons.append(f"verified_economics:{economics_points}/15")
    else:
        reasons.append("verified_economics:0/15")

    return min(100, int(score)), reasons


def _merge(queue_item: dict[str, object], evaluation: dict[str, object] | None) -> dict[str, object]:
    merged = dict(queue_item)
    if evaluation:
        for key in (
            "decision", "total_cost_nok", "conservative_resale_value_nok",
            "expected_profit_nok", "roi_percent", "maximum_safe_bid_nok",
            "missing_evidence",
        ):
            merged[key] = evaluation.get(key)
    score, score_reasons = _score(merged)
    merged["opportunity_score"] = score
    merged["score_reasons"] = score_reasons
    merged["recommendation"] = (
        "NUMERIC_REVIEW" if merged.get("decision") == "REVIEW_NUMBERS"
        else "COLLECT_EVIDENCE"
    )
    return merged


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default="data/opportunity_review_queue.json")
    parser.add_argument("--evaluations", default="data/economic_evaluation_queue.json")
    parser.add_argument("--output", default="data/top5_opportunities.json")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    queue_payload = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    queue = queue_payload.get("queue", [])
    if not isinstance(queue, list):
        raise ValueError("review queue must be a list")

    evaluations_path = Path(args.evaluations)
    evaluations_payload = json.loads(evaluations_path.read_text(encoding="utf-8")) if evaluations_path.exists() else {}
    evaluations = evaluations_payload.get("evaluations", [])
    by_id = {
        str(item.get("opportunity_id")): item
        for item in evaluations
        if isinstance(item, dict) and item.get("opportunity_id")
    } if isinstance(evaluations, list) else {}

    ranked = [
        _merge(item, by_id.get(str(item.get("opportunity_id"))))
        for item in queue
        if isinstance(item, dict)
    ]
    ranked.sort(key=lambda item: (-int(item["opportunity_score"]), int(item.get("priority") or 99), str(item.get("title") or "")))
    top = ranked[: max(1, args.limit)]

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "transparent operational ranking; verified economics only; missing values are never invented",
        "candidate_count": len(ranked),
        "top_count": len(top),
        "top_opportunities": top,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"candidate_count": len(ranked), "top_count": len(top), "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
