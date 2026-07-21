#!/usr/bin/env python3
"""Build and validate the economic-evidence registry for shortlisted opportunities.

This script never searches for, estimates, or invents prices and costs. It only
normalizes evidence already supplied by a human or an authorized data source.
Unknown values remain null and unverifiable comparables are excluded.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

COST_FIELDS = (
    "auction_fee_nok",
    "vat_nok",
    "transport_cost_nok",
    "dismantling_cost_nok",
    "storage_cost_nok",
    "repair_cost_nok",
    "other_costs_nok",
)
VAT_STATUSES = {"included", "excluded", "not_applicable"}


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return float(value)
    return None


def _existing_records(payload: object) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}
    records = payload.get("evidence", payload)
    if isinstance(records, dict):
        return {
            str(key): value
            for key, value in records.items()
            if isinstance(value, dict)
        }
    if isinstance(records, list):
        return {
            str(item.get("opportunity_id")): item
            for item in records
            if isinstance(item, dict) and item.get("opportunity_id")
        }
    return {}


def _verified_comparables(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, object]] = []
    seen: set[tuple[str, str, float]] = set()
    for item in value:
        if not isinstance(item, dict) or item.get("verified") is not True:
            continue
        source = str(item.get("source") or "").strip()
        url = str(item.get("url") or "").strip()
        price = _number(item.get("price_nok"))
        if not source or not url.startswith("https://") or price is None or price <= 0:
            continue
        key = (source.casefold(), url, price)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {"source": source, "url": url, "price_nok": price, "verified": True}
        )
    return result


def _normalize(item: dict[str, object], existing: dict[str, Any]) -> dict[str, object]:
    opportunity_id = str(item.get("opportunity_id") or "")
    comparables = _verified_comparables(
        existing.get("market_comparables", existing.get("market_comparables_nok"))
    )
    vat_status_raw = str(existing.get("vat_status") or "").strip().casefold()
    vat_status = vat_status_raw if vat_status_raw in VAT_STATUSES else None

    record: dict[str, object] = {
        "opportunity_id": opportunity_id,
        "title": item.get("title"),
        "url": item.get("url"),
        "market_comparables": comparables,
        "vat_status": vat_status,
        **{field: _number(existing.get(field)) for field in COST_FIELDS},
    }

    missing: list[str] = []
    if len(comparables) < 3:
        missing.append("three_verified_market_comparables")
    if record["auction_fee_nok"] is None:
        missing.append("auction_fee_nok")
    if vat_status is None:
        missing.append("vat_status")
    if record["vat_nok"] is None:
        missing.append("vat_nok")
    for field in COST_FIELDS[2:]:
        if record[field] is None:
            missing.append(field)

    record["verified"] = not missing
    record["missing_evidence"] = missing
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default="data/opportunity_review_queue.json")
    parser.add_argument("--existing", default="data/opportunity_evidence.json")
    parser.add_argument("--output", default="data/opportunity_evidence.json")
    args = parser.parse_args()

    queue_payload = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    queue = queue_payload.get("queue", [])
    if not isinstance(queue, list):
        raise ValueError("review queue must be a list")

    existing_path = Path(args.existing)
    existing_payload = (
        json.loads(existing_path.read_text(encoding="utf-8"))
        if existing_path.exists()
        else {}
    )
    existing = _existing_records(existing_payload)

    records: dict[str, dict[str, object]] = {}
    for item in queue:
        if not isinstance(item, dict) or not item.get("opportunity_id"):
            continue
        opportunity_id = str(item["opportunity_id"])
        records[opportunity_id] = _normalize(item, existing.get(opportunity_id, {}))

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "verified evidence only; unknown values remain null; no estimates are created",
        "evidence_count": len(records),
        "verified_count": sum(record["verified"] is True for record in records.values()),
        "evidence": records,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"evidence_count": len(records), "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
