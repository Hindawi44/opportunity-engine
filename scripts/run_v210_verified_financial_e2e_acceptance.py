#!/usr/bin/env python3
"""Deterministic V2.10 integration of verified V2.8 and V2.9 evidence."""
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from opportunity_engine.evidence_store import EvidenceRepository
from opportunity_engine.external_financial_bridge import collect_external_financial_evidence
from opportunity_engine.external_research.auction_cost_evidence import candidate_to_auction_cost_evidence
from opportunity_engine.external_research.comparable_evidence import candidate_to_market_price_evidence
from opportunity_engine.verified_financial_integration import integrate_verified_financial_evidence

OPPORTUNITY_ID = "e2e-financial-integration-test"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/validation/v2.10-financial-integration-e2e-acceptance.json")
    args = parser.parse_args()
    now = datetime.now(timezone.utc).isoformat()
    errors: list[str] = []

    comparables = (
        SimpleNamespace(title="Comparable A", url="https://market-a.no/item/1", price_nok=30000,
                        price_currency="NOK", source_name="Market A", observed_at=now, similarity_score=0.84),
        SimpleNamespace(title="Comparable B", url="https://market-b.no/item/2", price_nok=32000,
                        price_currency="NOK", source_name="Market B", observed_at=now, similarity_score=0.81),
        SimpleNamespace(title="Comparable C", url="https://market-c.no/item/3", price_nok=35000,
                        price_currency="NOK", source_name="Market C", observed_at=now, similarity_score=0.79),
    )
    costs = (
        ("auction_price", 10000, "https://auction.no/lot/1", False),
        ("auction_fee", 1500, "https://auction.no/terms/fee", False),
        ("vat", 2875, "https://auction.no/terms/vat", False),
        ("transport", 2200, "https://carrier.no/quote/1", False),
        ("dismantling", 1200, "https://service.no/quote/1", False),
        ("storage", 0, "https://warehouse.no/confirmation/1", True),
    )

    with tempfile.TemporaryDirectory(prefix="v210-") as directory:
        root = Path(directory) / "evidence"
        repository = EvidenceRepository(root)
        persisted_ids: list[str] = []
        for candidate in comparables:
            try:
                result = repository.upsert(candidate_to_market_price_evidence(candidate, OPPORTUNITY_ID))
                persisted_ids.append(result.evidence.evidence_id)
            except Exception as exc:
                errors.append(f"comparable:{exc}")
        for component, amount, url, zero in costs:
            try:
                result = repository.upsert(candidate_to_auction_cost_evidence({
                    "component": component,
                    "amount_nok": amount,
                    "currency": "NOK",
                    "source_url": url,
                    "source_name": "V2.10 deterministic fixture",
                    "observed_at": now,
                    "basis": f"Published {component} term",
                    "zero_cost_confirmed": zero,
                }, OPPORTUNITY_ID))
                persisted_ids.append(result.evidence.evidence_id)
            except Exception as exc:
                errors.append(f"{component}:{exc}")

        reloaded = []
        for evidence_id in persisted_ids:
            try:
                reloaded.append(repository.load(OPPORTUNITY_ID, evidence_id))
            except Exception as exc:
                errors.append(f"reload:{exc}")
        supplied = collect_external_financial_evidence(root).get(OPPORTUNITY_ID, {})
        decision = integrate_verified_financial_evidence(OPPORTUNITY_ID, supplied)

    summary = {
        "schema_version": "2.10",
        "opportunity_id": OPPORTUNITY_ID,
        "evidence_persisted": len(persisted_ids),
        "evidence_reloaded": len(reloaded),
        **decision.to_dict(),
        "true_acquisition_cost_calculated": decision.true_acquisition_cost_nok is not None,
        "conservative_resale_value_calculated": decision.conservative_resale_value_nok is not None,
        "expected_profit_calculated": decision.expected_profit_nok is not None,
        "roi_calculated": decision.roi_percent is not None,
        "financial_formula_modified": False,
        "errors": errors,
    }
    summary["status"] = "PASS" if (
        summary["evidence_persisted"] == 9
        and summary["evidence_reloaded"] == 9
        and summary["verified_comparable_count"] == 3
        and summary["verified_cost_component_count"] == 6
        and summary["market_evidence_status"] == "COMPLETE"
        and summary["cost_evidence_status"] == "COMPLETE"
        and summary["decision_gate"] == "READY_FOR_FINANCIAL_REVIEW"
        and summary["automatic_purchase_decision"] is False
        and summary["missing_required_evidence"] == []
        and not errors
    ) else "FAIL"

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
