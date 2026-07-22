#!/usr/bin/env python3
"""Build the concise top-five report from the unified P2 scoring output.

A backwards-compatible fallback remains for direct legacy use, but the production
pipeline supplies --scored so that ranking and recommendations come from one engine.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _legacy_score(item: dict[str, object]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    relevance = _number(item.get("relevance_score")) or 0.0
    relevance_points = min(35, max(0, round(relevance)))
    score += relevance_points
    reasons.append(f"relevance:{relevance_points}/35")
    priority_points = {1: 15, 2: 9, 3: 4}.get(item.get("priority"), 0)
    score += priority_points
    reasons.append(f"priority:{priority_points}/15")
    for key, label in (("asking_price_nok", "asking_price"), ("city", "location"), ("ends_at", "deadline")):
        present = _number(item.get(key)) is not None if key == "asking_price_nok" else bool(item.get(key))
        points = 5 if present else 0
        score += points
        reasons.append(f"{label}:{points}/5")
    missing = item.get("missing_evidence")
    missing_count = len(missing) if isinstance(missing, list) else 0
    evidence_points = max(0, 20 - min(20, missing_count * 3))
    score += evidence_points
    reasons.append(f"evidence:{evidence_points}/20")
    profit = _number(item.get("expected_profit_nok"))
    roi = _number(item.get("roi_percent"))
    economics_points = 0
    if profit is not None and roi is not None:
        economics_points = 15 if profit > 0 and roi >= 30 else 10 if profit > 0 and roi >= 15 else 4 if profit > 0 else 0
    score += economics_points
    reasons.append(f"verified_economics:{economics_points}/15")
    return min(100, int(score)), reasons


def _legacy_merge(queue_item: dict[str, object], evaluation: dict[str, object] | None) -> dict[str, object]:
    merged = dict(queue_item)
    if evaluation:
        for key in (
            "decision", "total_cost_nok", "conservative_resale_value_nok",
            "expected_profit_nok", "roi_percent", "maximum_safe_bid_nok",
            "missing_evidence",
        ):
            merged[key] = evaluation.get(key)
    score, score_reasons = _legacy_score(merged)
    merged["opportunity_score"] = score
    merged["score_reasons"] = score_reasons
    merged["recommendation"] = (
        "NUMERIC_REVIEW" if merged.get("decision") == "REVIEW_NUMBERS"
        else "COLLECT_EVIDENCE"
    )
    return merged


# Public compatibility names retained for the established unit-test and any external
# callers. Production P2 ranking does not use these helpers when --scored is supplied.
def _score(item: dict[str, object]) -> tuple[int, list[str]]:
    return _legacy_score(item)


def _merge(queue_item: dict[str, object], evaluation: dict[str, object] | None) -> dict[str, object]:
    return _legacy_merge(queue_item, evaluation)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default="data/opportunity_review_queue.json")
    parser.add_argument("--evaluations", default="data/economic_evaluation_queue.json")
    parser.add_argument("--scored", default=None, help="Unified P2 scoring output")
    parser.add_argument("--output", default="data/top5_opportunities.json")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    if args.scored:
        scored_payload = json.loads(Path(args.scored).read_text(encoding="utf-8"))
        opportunities = scored_payload.get("opportunities", [])
        if not isinstance(opportunities, list):
            raise ValueError("scored opportunities must be a list")
        ranked = [item for item in opportunities if isinstance(item, dict)]
        method = "unified P2 evidence-gated scoring; rejected candidates excluded from top report"
    else:
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
            _legacy_merge(item, by_id.get(str(item.get("opportunity_id"))))
            for item in queue
            if isinstance(item, dict)
        ]
        method = "legacy transparent operational ranking"

    ranked.sort(
        key=lambda item: (
            -float(item.get("opportunity_score") or 0),
            int(item.get("priority") or 99),
            str(item.get("title") or ""),
        )
    )
    actionable = [item for item in ranked if item.get("recommendation") != "REJECT"]
    top = actionable[: max(1, args.limit)]

    payload = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": method,
        "candidate_count": len(ranked),
        "actionable_count": len(actionable),
        "top_count": len(top),
        "top_opportunities": top,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"candidate_count": len(ranked), "actionable_count": len(actionable), "top_count": len(top), "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
