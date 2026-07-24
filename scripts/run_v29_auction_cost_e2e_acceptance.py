#!/usr/bin/env python3
"""Deterministic V2.9 auction cost and logistics acceptance run."""
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.evidence_store import EvidenceRepository
from opportunity_engine.external_financial_bridge import collect_external_financial_evidence
from opportunity_engine.external_research.auction_cost_evidence import candidate_to_auction_cost_evidence


OPPORTUNITY_ID = "e2e-auction-cost-test"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/validation/v2.9-auction-cost-e2e-acceptance.json")
    args = parser.parse_args()
    now = datetime.now(timezone.utc).isoformat()
    rows = (
        ("auction_price", 10000, "https://auction-one.no/lot/1", False),
        ("auction_fee", 1500, "https://auction-one.no/terms/fees", False),
        ("vat", 2875, "https://auction-one.no/terms/vat", False),
        ("transport", 2200, "https://carrier-one.no/quote/1", False),
        ("dismantling", 1200, "https://service-one.no/quote/1", False),
        ("storage", 0, "https://warehouse-one.no/confirmation/1", True),
    )
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as directory:
        repository = EvidenceRepository(Path(directory) / "evidence")
        for component, amount, url, zero in rows:
            try:
                evidence = candidate_to_auction_cost_evidence(
                    {
                        "component": component,
                        "amount_nok": amount,
                        "currency": "NOK",
                        "source_url": url,
                        "source_name": "V2.9 deterministic fixture",
                        "observed_at": now,
                        "basis": f"Published {component} term",
                        "zero_cost_confirmed": zero,
                    },
                    OPPORTUNITY_ID,
                )
                repository.upsert(evidence)
            except Exception as exc:
                errors.append(f"{component}:{exc}")
        reloaded = repository.list_for_opportunity(OPPORTUNITY_ID)
        bridged = collect_external_financial_evidence(Path(directory) / "evidence").get(OPPORTUNITY_ID, {})

    required = (
        "auction_price_nok",
        "auction_fee_nok",
        "vat_nok",
        "transport_cost_nok",
        "dismantling_cost_nok",
        "storage_cost_nok",
    )
    verified = sum(field in bridged for field in required)
    status = "PASS" if len(reloaded) == 6 and verified == 6 and not errors else "FAIL"
    summary = {
        "schema_version": "2.9",
        "opportunity_id": OPPORTUNITY_ID,
        "cost_candidates_received": 6,
        "valid_cost_candidates": 6 - len(errors),
        "evidence_persisted": len(reloaded),
        "evidence_reloaded": len(reloaded),
        "verified_cost_component_count": verified,
        "cost_evidence_status": "COMPLETE" if verified == 6 else "INCOMPLETE",
        "true_acquisition_cost_nok": sum(float(bridged[field]) for field in required) if verified == 6 else None,
        "financial_formula_modified": False,
        "financial_score_status": "PRELIMINARY",
        "errors": errors,
        "status": status,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
