#!/usr/bin/env python3
"""Build a conservative market-evidence registry from discovered comparables.

The registry separates candidate evidence from verified evidence. It removes
obvious price outliers, requires multiple independent domains, and creates a
manual-review queue. No market value is marked verified automatically.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from statistics import median
from typing import Any

_MIN_COMPARABLES = 3
_MIN_DOMAINS = 2
_OUTLIER_RATIO = 2.5


def _number(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _domain(candidate: dict[str, Any]) -> str:
    return str(candidate.get("domain") or "").strip().casefold()


def _remove_outliers(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    priced = [(candidate, _number(candidate.get("price_nok"))) for candidate in candidates]
    priced = [(candidate, price) for candidate, price in priced if price is not None]
    if len(priced) < 3:
        return [candidate for candidate, _ in priced], []

    center = median(price for _, price in priced)
    lower = center / _OUTLIER_RATIO
    upper = center * _OUTLIER_RATIO
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for candidate, price in priced:
        if lower <= price <= upper:
            accepted.append(candidate)
        else:
            rejected.append({
                **candidate,
                "evidence_rejection_reason": "price_outlier",
                "median_reference_nok": center,
                "accepted_range_nok": [round(lower, 2), round(upper, 2)],
            })
    return accepted, rejected


def _build_record(raw: dict[str, Any]) -> dict[str, Any]:
    candidates = [item for item in raw.get("candidates", []) if isinstance(item, dict)]
    accepted, outliers = _remove_outliers(candidates)
    prices = [_number(item.get("price_nok")) for item in accepted]
    clean_prices = [price for price in prices if price is not None]
    domains = sorted({_domain(item) for item in accepted if _domain(item)})

    enough_comparables = len(accepted) >= _MIN_COMPARABLES
    enough_domains = len(domains) >= _MIN_DOMAINS
    candidate_value = median(clean_prices) if enough_comparables and enough_domains else None

    review_reasons: list[str] = []
    if len(accepted) < _MIN_COMPARABLES:
        review_reasons.append("fewer_than_3_comparables")
    if len(domains) < _MIN_DOMAINS:
        review_reasons.append("fewer_than_2_independent_domains")
    if any(str(item.get("quantity_status")) == "UNKNOWN" for item in accepted):
        review_reasons.append("quantity_not_confirmed_for_all_comparables")
    if outliers:
        review_reasons.append("price_outliers_removed")

    return {
        "opportunity_id": raw.get("opportunity_id"),
        "title": raw.get("title"),
        "asking_price_nok": raw.get("asking_price_nok"),
        "candidate_comparable_count": len(candidates),
        "accepted_comparable_count": len(accepted),
        "independent_domain_count": len(domains),
        "independent_domains": domains,
        "candidate_market_value_nok": candidate_value,
        "market_value_verified": False,
        "verified_market_value_nok": None,
        "evidence_status": "REVIEW_REQUIRED" if candidate_value is not None else "INSUFFICIENT_EVIDENCE",
        "review_reasons": review_reasons,
        "accepted_comparables": accepted,
        "outlier_count": len(outliers),
        "outliers": outliers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/market_price_candidates.json")
    parser.add_argument("--output", default="data/market_evidence_registry.json")
    parser.add_argument("--review-output", default="data/market_evidence_review_queue.json")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    opportunities = payload.get("opportunities", [])
    if not isinstance(opportunities, list):
        raise ValueError("market price opportunities must be a list")

    records = [_build_record(item) for item in opportunities if isinstance(item, dict)]
    review_queue = [
        {
            "opportunity_id": item["opportunity_id"],
            "title": item["title"],
            "candidate_market_value_nok": item["candidate_market_value_nok"],
            "evidence_status": item["evidence_status"],
            "review_reasons": item["review_reasons"],
            "accepted_comparable_count": item["accepted_comparable_count"],
            "independent_domain_count": item["independent_domain_count"],
            "accepted_comparables": item["accepted_comparables"],
        }
        for item in records
        if item["evidence_status"] == "REVIEW_REQUIRED"
    ]

    now = datetime.now(timezone.utc).isoformat()
    output_payload = {
        "schema_version": 1,
        "generated_at": now,
        "policy": {
            "minimum_comparables": _MIN_COMPARABLES,
            "minimum_independent_domains": _MIN_DOMAINS,
            "outlier_ratio": _OUTLIER_RATIO,
            "automatic_verification": False,
        },
        "opportunity_count": len(records),
        "review_required_count": len(review_queue),
        "verified_count": 0,
        "records": records,
    }
    review_payload = {
        "schema_version": 1,
        "generated_at": now,
        "queue_count": len(review_queue),
        "queue": review_queue,
    }

    output = Path(args.output)
    review_output = Path(args.review_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    review_output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    review_output.write_text(json.dumps(review_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "review_output": str(review_output),
        "opportunity_count": len(records),
        "review_required_count": len(review_queue),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
