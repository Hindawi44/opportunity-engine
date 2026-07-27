"""Verified acquisition-cost bridge for the Clothing Inventory single-case runner.

This module reuses the existing V2.9 auction-cost evidence contract and the V2.10
verified-financial integration boundary. Only explicit, source-traceable records
marked ``verified: true`` can enter the financial calculation. Missing components
remain missing and no automatic commercial decision is produced.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from opportunity_engine.external_research.auction_cost_evidence import (
    candidate_to_auction_cost_evidence,
)
from opportunity_engine.verified_financial_integration import (
    integrate_verified_financial_evidence,
)

_REQUIRED_COST_FIELDS = (
    "auction_price_nok",
    "auction_fee_nok",
    "vat_nok",
    "transport_cost_nok",
    "dismantling_cost_nok",
    "storage_cost_nok",
)


def _records(payload: object) -> list[dict[str, Any]]:
    """Extract cost records from supported machine-readable payloads."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        raise ValueError("cost payload must be a list or object")

    for key in ("costs", "cost_components", "acquisition_costs"):
        direct = payload.get(key)
        if isinstance(direct, list):
            return [item for item in direct if isinstance(item, dict)]
    return []


def evaluate_verified_acquisition_costs(
    payload: object,
    *,
    opportunity_id: str,
) -> dict[str, Any]:
    """Validate explicit verified cost observations through the V2.9 contract."""
    raw_records = _records(payload)
    accepted_by_field: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []

    for index, record in enumerate(raw_records):
        if record.get("verified") is not True:
            rejected.append(
                {
                    "index": index,
                    "component": record.get("component"),
                    "source_url": record.get("source_url") or record.get("url"),
                    "reasons": ["cost_component_not_explicitly_verified"],
                }
            )
            continue

        try:
            evidence = candidate_to_auction_cost_evidence(record, opportunity_id)
            financial_field = str(evidence.metadata.get("financial_field") or "")
            component = str(evidence.metadata.get("cost_component") or "")
            if financial_field not in _REQUIRED_COST_FIELDS:
                raise ValueError("unsupported financial field")
            if financial_field in accepted_by_field:
                rejected.append(
                    {
                        "index": index,
                        "component": component,
                        "source_url": evidence.source_url,
                        "reasons": [f"duplicate_cost_component:{component}"],
                    }
                )
                continue
            if not evidence.observations:
                raise ValueError("validated cost evidence has no observation")
            observation = evidence.observations[0]
            amount = observation.numeric_value
            if amount is None:
                raise ValueError("validated cost evidence has no numeric value")

            accepted_by_field[financial_field] = {
                "component": component,
                "financial_field": financial_field,
                "amount_nok": float(amount),
                "currency": observation.currency,
                "source_name": evidence.source_name,
                "source_url": evidence.source_url,
                "observed_at": evidence.metadata.get("observed_at"),
                "basis": observation.notes,
                "zero_cost_confirmed": bool(
                    evidence.metadata.get("zero_cost_confirmed")
                ),
                "verified": True,
                "contract_version": "2.9",
            }
        except (TypeError, ValueError) as exc:
            rejected.append(
                {
                    "index": index,
                    "component": record.get("component"),
                    "source_url": record.get("source_url") or record.get("url"),
                    "reasons": [f"invalid_verified_cost_component:{exc}"],
                }
            )

    missing_fields = [
        field for field in _REQUIRED_COST_FIELDS if field not in accepted_by_field
    ]
    complete = not missing_fields
    true_acquisition_cost = (
        round(
            sum(float(accepted_by_field[field]["amount_nok"]) for field in _REQUIRED_COST_FIELDS),
            2,
        )
        if complete
        else None
    )

    return {
        "schema_version": "single-case-acquisition-costs-v1",
        "required_cost_components": list(_REQUIRED_COST_FIELDS),
        "records_received": len(raw_records),
        "accepted_count": len(accepted_by_field),
        "rejected_count": len(rejected),
        "status": "COMPLETE" if complete else "INCOMPLETE",
        "missing_required_cost_fields": missing_fields,
        "true_acquisition_cost_nok": true_acquisition_cost,
        "accepted": [accepted_by_field[field] for field in _REQUIRED_COST_FIELDS if field in accepted_by_field],
        "rejected": rejected,
    }


def apply_verified_acquisition_costs(
    report: dict[str, Any],
    payload: object,
) -> dict[str, Any]:
    """Attach V2.9 costs and rerun the existing V2.10 financial boundary safely."""
    enriched = deepcopy(report)
    dossier = enriched.get("dossier")
    eligibility = enriched.get("eligibility")
    if not isinstance(dossier, dict) or not isinstance(eligibility, dict):
        raise ValueError("single-case report is missing dossier or eligibility data")

    opportunity_id = str(
        dossier.get("opportunity_id") or "clothing-inventory-single-case"
    )
    costs = evaluate_verified_acquisition_costs(
        payload,
        opportunity_id=opportunity_id,
    )
    enriched["acquisition_cost_evidence"] = costs

    if eligibility.get("eligible_for_analysis") is True:
        market = enriched.get("market_comparables")
        accepted_market = (
            market.get("accepted", [])
            if isinstance(market, dict) and market.get("status") == "COMPLETE"
            else []
        )
        supplied: dict[str, Any] = {
            "market_comparables": [
                {
                    "verified": True,
                    "price_nok": item.get("price_nok"),
                    "source": item.get("source_name"),
                    "url": item.get("url"),
                }
                for item in accepted_market
                if isinstance(item, dict)
            ]
        }
        accepted_costs = {
            item["financial_field"]: item["amount_nok"]
            for item in costs["accepted"]
            if isinstance(item, dict)
            and item.get("financial_field") in _REQUIRED_COST_FIELDS
        }
        supplied.update(
            {field: accepted_costs.get(field) for field in _REQUIRED_COST_FIELDS}
        )

        financial = integrate_verified_financial_evidence(
            opportunity_id,
            supplied,
        )
        enriched["financial_integration"] = financial.to_dict()
        enriched["analysis_invoked"] = True
        enriched["final_outcome"] = (
            "ANALYSIS_READY"
            if financial.decision_gate == "READY_FOR_FINANCIAL_REVIEW"
            else "EVIDENCE_REQUIRED"
        )
    else:
        enriched["financial_integration"] = {
            "invoked": False,
            "decision_gate": "EVIDENCE_REQUIRED",
            "reason": "eligibility_gate_blocked",
        }
        enriched["analysis_invoked"] = False
        enriched["final_outcome"] = "EVIDENCE_REQUIRED"

    enriched["automatic_purchase_decision"] = False
    enriched["automatic_bid"] = False
    enriched["automatic_contact"] = False
    enriched["automatic_payment"] = False
    return enriched
