#!/usr/bin/env python3
"""Connect persisted External Evidence to Financial Score and Final Investment Score."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opportunity_engine.external_financial_bridge import (
    collect_external_financial_evidence,
    merge_evidence,
)
from build_economic_evaluation_queue import _evaluate
from build_scored_opportunities import score_opportunity


def _read(path: Path, default: object) -> object:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build evidence-gated financial and final scores")
    parser.add_argument("--queue", default="data/opportunity_review_queue.json")
    parser.add_argument("--evidence-dir", default="data/evidence")
    parser.add_argument("--existing-evidence", default="data/opportunity_evidence.json")
    parser.add_argument("--evidence-output", default="data/opportunity_evidence.json")
    parser.add_argument("--evaluations-output", default="data/economic_evaluation_queue.json")
    parser.add_argument("--scores-output", default="data/scored_opportunities.json")
    parser.add_argument("--summary-output", default="data/validation/v2.7.2.5-financial-final-score.json")
    parser.add_argument("--schema-version", default="2.7.2.5")
    args = parser.parse_args()

    queue_payload = _read(Path(args.queue), {"queue": []})
    queue = queue_payload.get("queue", []) if isinstance(queue_payload, dict) else []
    if not isinstance(queue, list):
        raise ValueError("review queue must contain a list")

    external = collect_external_financial_evidence(args.evidence_dir)
    existing = _read(Path(args.existing_evidence), {})
    evidence_payload = merge_evidence(existing, external)
    evidence_path = Path(args.evidence_output)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(evidence_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    records = evidence_payload["evidence"]
    evaluations = [_evaluate(item, records) for item in queue if isinstance(item, dict)]
    evaluation_payload = {
        "schema_version": 3,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "External Evidence bridged into conservative evidence-gated economics; missing costs remain null",
        "evaluation_count": len(evaluations),
        "ready_for_numeric_review_count": sum(item["decision"] == "REVIEW_NUMBERS" for item in evaluations),
        "evidence_required_count": sum(item["decision"] == "EVIDENCE_REQUIRED" for item in evaluations),
        "evaluations": evaluations,
    }
    evaluation_path = Path(args.evaluations_output)
    evaluation_path.parent.mkdir(parents=True, exist_ok=True)
    evaluation_path.write_text(json.dumps(evaluation_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    by_id = {str(item.get("opportunity_id")): item for item in evaluations}
    scored = [
        score_opportunity(item, by_id.get(str(item.get("opportunity_id"))))
        for item in queue
        if isinstance(item, dict)
    ]
    scored.sort(key=lambda item: -float(item["opportunity_score"]))
    scores_payload = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "External Evidence -> Financial Score -> evidence-gated Final Investment Score",
        "candidate_count": len(scored),
        "opportunities": scored,
    }
    scores_path = Path(args.scores_output)
    scores_path.parent.mkdir(parents=True, exist_ok=True)
    scores_path.write_text(json.dumps(scores_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary_records: list[dict[str, Any]] = []
    for item in scored:
        components = item.get("score_components") if isinstance(item.get("score_components"), dict) else {}
        opportunity_id = str(item.get("opportunity_id"))
        market_comparables = records.get(opportunity_id, {}).get("market_comparables", [])
        verified_count = len(market_comparables) if isinstance(market_comparables, list) else 0
        summary_records.append({
            "opportunity_id": item.get("opportunity_id"),
            "title": item.get("title"),
            "verified_comparables": verified_count,
            "verified_comparable_count": verified_count,
            "financial_score": components.get("verified_economics", 0.0),
            "final_investment_score": item.get("opportunity_score"),
            "grade": item.get("score_grade"),
            "recommendation": item.get("recommendation"),
            "decision": item.get("decision"),
            "score_status": "NUMERIC" if item.get("decision") == "REVIEW_NUMBERS" else "PRELIMINARY",
            "expected_profit_nok": item.get("expected_profit_nok"),
            "roi_percent": item.get("roi_percent"),
            "missing_evidence": item.get("missing_evidence"),
        })
    summary = {
        "schema_version": args.schema_version,
        "external_evidence_opportunities": len(external),
        "external_comparables": sum(len(item.get("market_comparables", [])) for item in external.values()),
        "financial_scores_calculated": len(summary_records),
        "numeric_financial_scores": sum(record["decision"] == "REVIEW_NUMBERS" for record in summary_records),
        "final_investment_scores_calculated": len(summary_records),
        "records": summary_records,
    }
    summary_path = Path(args.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
