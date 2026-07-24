#!/usr/bin/env python3
"""Validate one real opportunity snapshot without inventing missing evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from opportunity_engine.verified_financial_integration import integrate_verified_financial_evidence


REQUIRED_COST_FIELDS = (
    "auction_price_nok",
    "auction_fee_nok",
    "vat_nok",
    "transport_cost_nok",
    "dismantling_cost_nok",
    "storage_cost_nok",
)


def _read(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("live snapshot must be a JSON object")
    return payload


def build_report(snapshot: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    opportunity_id = str(snapshot.get("opportunity_id") or "").strip()
    source = snapshot.get("source") if isinstance(snapshot.get("source"), dict) else {}
    source_url = str(source.get("url") or "").strip()
    asking_price = source.get("asking_price_nok")
    market_sources = snapshot.get("market_price_sources")
    market_sources = market_sources if isinstance(market_sources, list) else []
    costs = snapshot.get("verified_cost_evidence")
    costs = costs if isinstance(costs, dict) else {}

    if not opportunity_id:
        errors.append("missing opportunity_id")
    if not source_url.startswith("https://"):
        errors.append("live source must be public HTTPS")
    if not isinstance(asking_price, (int, float)) or isinstance(asking_price, bool) or asking_price <= 0:
        errors.append("asking price must be positive")

    valid_market_sources = sum(
        isinstance(item, dict)
        and str(item.get("source_url") or "").startswith("https://")
        and bool(str(item.get("source_name") or "").strip())
        for item in market_sources
    )
    verified_cost_count = sum(costs.get(field) is not None for field in REQUIRED_COST_FIELDS)

    # V2.8 values cannot be accepted until the live lot quantity and price units are verified.
    financial_evidence = {
        "market_comparables": [],
        **{field: costs.get(field) for field in REQUIRED_COST_FIELDS},
    }
    integration = integrate_verified_financial_evidence(opportunity_id, financial_evidence)
    missing = sorted(set(snapshot.get("blocking_missing_evidence", [])) | set(integration["missing_required_evidence"]))

    trace_complete = (
        bool(opportunity_id)
        and source_url.startswith("https://")
        and valid_market_sources >= 3
        and "auction_price_nok" not in missing
    )
    ready = integration["decision_gate"] == "READY_FOR_FINANCIAL_REVIEW"

    return {
        "schema_version": "2.11",
        "opportunity_id": opportunity_id,
        "live_source": source.get("name"),
        "live_source_url": source_url,
        "live_snapshot_valid": not errors,
        "market_sources_observed": valid_market_sources,
        "verified_comparable_count": integration["verified_comparable_count"],
        "verified_cost_component_count": verified_cost_count,
        "market_status": integration["market_evidence_status"],
        "cost_status": integration["cost_evidence_status"],
        "true_acquisition_cost_nok": integration["true_acquisition_cost_nok"],
        "conservative_resale_value_nok": integration["conservative_resale_value_nok"],
        "expected_profit_nok": integration["expected_profit_nok"],
        "roi_percent": integration["roi_percent"],
        "decision_gate": integration["decision_gate"],
        "automatic_purchase_decision": False,
        "evidence_trace_complete": trace_complete,
        "missing_required_evidence": missing,
        "errors": errors,
        "status": "PASS" if ready and trace_complete and not errors else "IN_PROGRESS",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", default="data/live_validation/v2.11-auksjonen-berryalloc-route66.json")
    parser.add_argument("--output", default="data/validation/v2.11-live-opportunity-validation.json")
    args = parser.parse_args()

    report = build_report(_read(Path(args.snapshot)))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    # IN_PROGRESS is a truthful live-data state, not a code failure.
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
