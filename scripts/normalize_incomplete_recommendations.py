#!/usr/bin/env python3
"""Prevent incomplete financial evidence from being mislabeled as an economic rejection.

This post-processing step preserves the calculated preliminary score, but changes the
recommendation to EVIDENCE_REQUIRED whenever the upstream economic decision is
EVIDENCE_REQUIRED. A true REJECT remains reserved for opportunities whose completed
financial inputs prove an unacceptable result.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def normalize_scored_payload(payload: dict[str, Any]) -> dict[str, Any]:
    opportunities = payload.get("opportunities")
    if not isinstance(opportunities, list):
        return payload

    for item in opportunities:
        if not isinstance(item, dict):
            continue
        if item.get("decision") == "EVIDENCE_REQUIRED":
            item["recommendation"] = "EVIDENCE_REQUIRED"
            item["recommendation_ar"] = "يحتاج أدلة"
            item["score_status"] = "PRELIMINARY"
            item["requires_human_approval"] = False
        else:
            item["score_status"] = "FINAL"

    payload["evidence_required_count"] = sum(
        item.get("recommendation") == "EVIDENCE_REQUIRED"
        for item in opportunities
        if isinstance(item, dict)
    )
    payload["buy_review_count"] = sum(
        item.get("recommendation") == "BUY_REVIEW"
        for item in opportunities
        if isinstance(item, dict)
    )
    payload["monitor_count"] = sum(
        item.get("recommendation") == "MONITOR"
        for item in opportunities
        if isinstance(item, dict)
    )
    payload["reject_count"] = sum(
        item.get("recommendation") == "REJECT"
        for item in opportunities
        if isinstance(item, dict)
    )
    return payload


def normalize_summary_payload(payload: dict[str, Any]) -> dict[str, Any]:
    records = payload.get("records")
    if not isinstance(records, list):
        return payload

    for record in records:
        if not isinstance(record, dict):
            continue
        if record.get("decision") == "EVIDENCE_REQUIRED":
            record["recommendation"] = "EVIDENCE_REQUIRED"
            record["recommendation_ar"] = "يحتاج أدلة"
            record["score_status"] = "PRELIMINARY"
        else:
            record["score_status"] = "FINAL"

    payload["evidence_required_count"] = sum(
        record.get("recommendation") == "EVIDENCE_REQUIRED"
        for record in records
        if isinstance(record, dict)
    )
    payload["economic_reject_count"] = sum(
        record.get("recommendation") == "REJECT"
        for record in records
        if isinstance(record, dict)
    )
    payload["status_policy"] = (
        "Missing financial evidence produces EVIDENCE_REQUIRED/PRELIMINARY, not REJECT. "
        "REJECT is reserved for completed economics with an unacceptable result."
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores", default="data/scored_opportunities.json")
    parser.add_argument("--summary", default="data/validation/v2.7.2.5-financial-final-score.json")
    args = parser.parse_args()

    scores_path = Path(args.scores)
    summary_path = Path(args.summary)

    scores = normalize_scored_payload(_read(scores_path))
    summary = normalize_summary_payload(_read(summary_path))

    if scores:
        scores_path.write_text(
            json.dumps(scores, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if summary:
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(json.dumps({
        "evidence_required_count": summary.get("evidence_required_count", 0),
        "economic_reject_count": summary.get("economic_reject_count", 0),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
