#!/usr/bin/env python3
"""Prepare evidence-gated economic evaluations for shortlisted opportunities.

The script never invents resale values, fees, VAT, transport, dismantling, repair,
or storage costs. Missing inputs remain null and block a buy recommendation.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_FIELDS = (
    "market_comparables_nok",
    "auction_fee_nok",
    "vat_nok",
    "transport_cost_nok",
    "dismantling_cost_nok",
    "storage_cost_nok",
    "repair_cost_nok",
    "other_costs_nok",
)


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return float(value)
    return None


def _evidence_records(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {}
    records = payload.get("evidence", payload)
    return records if isinstance(records, dict) else {}


def _verified_comparable_prices(supplied: dict[str, object]) -> list[float]:
    structured = supplied.get("market_comparables")
    if isinstance(structured, list):
        prices: list[float] = []
        for item in structured:
            if not isinstance(item, dict) or item.get("verified") is not True:
                continue
            source = str(item.get("source") or "").strip()
            url = str(item.get("url") or "").strip()
            price = _number(item.get("price_nok"))
            if source and url.startswith("https://") and price is not None and price > 0:
                prices.append(price)
        return prices

    # Backwards compatibility for already-created evidence files.
    legacy = supplied.get("market_comparables_nok")
    if isinstance(legacy, list):
        return [float(value) for value in legacy if _number(value) is not None]
    return []


def _evaluate(item: dict[str, object], evidence: dict[str, object]) -> dict[str, object]:
    opportunity_id = str(item.get("opportunity_id") or "")
    supplied = evidence.get(opportunity_id)
    supplied = supplied if isinstance(supplied, dict) else {}

    valid_comparables = _verified_comparable_prices(supplied)
    values: dict[str, object] = {
        "market_comparables_nok": valid_comparables,
        **{field: _number(supplied.get(field)) for field in REQUIRED_FIELDS[1:]},
    }
    missing = [field for field in REQUIRED_FIELDS[1:] if values[field] is None]
    if len(valid_comparables) < 3:
        missing.insert(0, "three_verified_market_comparables")

    asking_price = _number(item.get("asking_price_nok"))
    if asking_price is None:
        missing.append("asking_price_nok")

    result: dict[str, object] = {
        "opportunity_id": opportunity_id,
        "title": item.get("title"),
        "url": item.get("url"),
        "priority": item.get("priority"),
        "asking_price_nok": asking_price,
        "evidence": values,
        "missing_evidence": sorted(set(missing)),
        "decision": "EVIDENCE_REQUIRED",
        "total_cost_nok": None,
        "conservative_resale_value_nok": None,
        "expected_profit_nok": None,
        "roi_percent": None,
        "maximum_safe_bid_nok": None,
    }

    if missing:
        return result

    conservative_resale = min(valid_comparables)
    operating_costs = sum(float(values[field]) for field in REQUIRED_FIELDS[1:])
    total_cost = float(asking_price) + operating_costs
    profit = conservative_resale - total_cost
    roi = (profit / total_cost * 100.0) if total_cost > 0 else None

    result.update(
        {
            "decision": "REVIEW_NUMBERS",
            "total_cost_nok": round(total_cost, 2),
            "conservative_resale_value_nok": round(conservative_resale, 2),
            "expected_profit_nok": round(profit, 2),
            "roi_percent": round(roi, 2) if roi is not None else None,
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default="data/opportunity_review_queue.json")
    parser.add_argument("--evidence", default="data/opportunity_evidence.json")
    parser.add_argument("--output", default="data/economic_evaluation_queue.json")
    args = parser.parse_args()

    queue_payload = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    queue = queue_payload.get("queue", [])
    if not isinstance(queue, list):
        raise ValueError("review queue must be a list")

    evidence_path = Path(args.evidence)
    evidence_payload = (
        json.loads(evidence_path.read_text(encoding="utf-8"))
        if evidence_path.exists()
        else {}
    )
    evidence = _evidence_records(evidence_payload)

    evaluations = [_evaluate(item, evidence) for item in queue if isinstance(item, dict)]
    payload = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_queue": args.queue,
        "evidence_source": args.evidence,
        "method": "verified-evidence-gated conservative economics; missing values remain null and block recommendations",
        "evaluation_count": len(evaluations),
        "ready_for_numeric_review_count": sum(item["decision"] == "REVIEW_NUMBERS" for item in evaluations),
        "evidence_required_count": sum(item["decision"] == "EVIDENCE_REQUIRED" for item in evaluations),
        "evaluations": evaluations,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"evaluation_count": len(evaluations), "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
