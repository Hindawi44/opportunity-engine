#!/usr/bin/env python3
"""Execute the first preserved real Clothing Inventory investment report.

The case is a publicly traceable, completed Auksjonen.no lot containing 25
Blåkläder 3463 hybrid jackets. The runner reuses the merged single-case
Discovery, evidence, financial, scoring and decision contracts. It does not
convert unknown auction fees, VAT, transport, dismantling or storage into zero.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opportunity_engine.discovery.models import DiscoveryCandidate
from scripts.run_clothing_inventory_single_case import (
    enrich_with_comparables,
    enrich_with_costs,
    enrich_with_decision,
    run_candidate,
    write_report_outputs,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = (
    REPOSITORY_ROOT / "data/validation/first-real-clothing-inventory-report"
)
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT_DIR / "generated"
EXECUTION_TIME = datetime(2026, 7, 27, 6, 55, tzinfo=timezone.utc)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def load_candidate(path: Path) -> tuple[DiscoveryCandidate, dict[str, Any]]:
    """Load only explicit candidate facts; preserve execution metadata separately."""
    payload = _load_json(path)
    candidate = DiscoveryCandidate(
        title=str(payload["title"]),
        url=str(payload["url"]),
        source=str(payload["source"]),
        discovered_at=str(payload["discovered_at"]),
        text=str(payload.get("text") or ""),
        location=(str(payload["location"]) if payload.get("location") else None),
        quantity=(int(payload["quantity"]) if payload.get("quantity") is not None else None),
        price_nok=(
            float(payload["price_nok"]) if payload.get("price_nok") is not None else None
        ),
        contact=(str(payload["contact"]) if payload.get("contact") else None),
    )
    return candidate, payload


def build_first_real_report(input_dir: Path = DEFAULT_INPUT_DIR) -> dict[str, Any]:
    """Run the preserved public case through every merged decision boundary."""
    candidate, candidate_metadata = load_candidate(input_dir / "candidate.json")
    comparables = _load_json(input_dir / "verified-comparables.json")
    costs = _load_json(input_dir / "verified-acquisition-costs.json")

    outcome = run_candidate(candidate)
    report = outcome.to_dict()
    report.update(
        {
            "domain": "CLOTHING_INVENTORY",
            "final_outcome": outcome.outcome_type,
            "execution_mode": "PRESERVED_REAL_PUBLIC_CASE",
            "automatic_purchase_decision": False,
            "automatic_bid": False,
            "automatic_contact": False,
            "automatic_payment": False,
            "real_execution": {
                "report_version": "first-real-clothing-investment-report-v1",
                "executed_at": EXECUTION_TIME.isoformat(),
                "sale_status": candidate_metadata.get("sale_status"),
                "auction_ended_on": candidate_metadata.get("auction_ended_on"),
                "evidence_note": candidate_metadata.get("evidence_note"),
                "comparable_method": comparables.get("valuation_method"),
                "comparable_warning": comparables.get("warning"),
                "cost_status_note": costs.get("status_note"),
            },
        }
    )

    canonical = report.get("canonical_opportunity")
    if isinstance(canonical, dict):
        source = canonical.get("source")
        if isinstance(source, dict):
            source["listing_status"] = "ENDED"

    report = enrich_with_comparables(report, comparables, now=EXECUTION_TIME)
    report = enrich_with_costs(report, costs)
    report = enrich_with_decision(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute the first preserved real Clothing Inventory report."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    report = build_first_real_report(args.input_dir)
    paths = write_report_outputs(report, args.output_dir)
    for label, path in paths.items():
        print(f"{label}: {path}")
    print(f"final_outcome: {report.get('final_outcome')}")
    print(f"final_decision: {report.get('final_decision')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
