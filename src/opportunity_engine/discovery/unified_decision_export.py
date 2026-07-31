"""Export official decision intelligence through Unified Opportunity Contract V1."""
from __future__ import annotations

from collections import Counter
from typing import Any

from opportunity_engine.discovery.unified_opportunity_contract import (
    UnifiedOpportunityContractError,
    UnifiedOpportunityContractV1,
)


EXPORT_SCHEMA_VERSION = "unified-opportunity-contract-export-v1"


def build_unified_decision_export(
    decision_payload: dict[str, Any],
    *,
    market: str = "NO",
) -> dict[str, Any]:
    """Build an additive sidecar while preserving official decisions and scores."""
    if not isinstance(decision_payload, dict):
        raise UnifiedOpportunityContractError("decision payload must be an object")

    decisions = decision_payload.get("decisions")
    if not isinstance(decisions, list):
        raise UnifiedOpportunityContractError("decision payload decisions must be a list")

    contracts: list[dict[str, Any]] = []
    source_ids: list[str] = []
    for index, record in enumerate(decisions):
        if not isinstance(record, dict):
            raise UnifiedOpportunityContractError(
                f"decision payload decisions[{index}] must be an object"
            )
        contract = UnifiedOpportunityContractV1.from_decision_intelligence_record(
            record,
            market=market,
        )
        contract_payload = contract.to_dict()

        if contract_payload["final_decision"] != record.get("final_decision"):
            raise UnifiedOpportunityContractError(
                f"final_decision changed for {contract.opportunity_id}"
            )
        if contract_payload["risk"]["opportunity_score"] != record.get(
            "opportunity_score"
        ):
            raise UnifiedOpportunityContractError(
                f"opportunity_score changed for {contract.opportunity_id}"
            )
        if record.get("recommendation") is not None and record.get(
            "recommendation"
        ) != record.get("final_decision"):
            raise UnifiedOpportunityContractError(
                f"legacy recommendation contradicts final_decision for {contract.opportunity_id}"
            )

        contracts.append(contract_payload)
        source_ids.append(contract.opportunity_id)

    if len(source_ids) != len(set(source_ids)):
        raise UnifiedOpportunityContractError("duplicate opportunity_id in decision payload")

    declared_count = decision_payload.get("decision_count")
    if declared_count is not None and declared_count != len(contracts):
        raise UnifiedOpportunityContractError(
            "decision_count does not match the number of decision records"
        )

    decision_counts = Counter(
        str(contract["final_decision"]) for contract in contracts
    )
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "contract_schema_version": (
            contracts[0]["schema_version"] if contracts else "unified-opportunity-contract-v1"
        ),
        "source_schema_version": decision_payload.get("schema_version"),
        "source_generated_at": decision_payload.get("generated_at"),
        "source_official_decision_field": decision_payload.get(
            "official_decision_field"
        ),
        "market": market,
        "opportunity_count": len(contracts),
        "decision_counts": dict(sorted(decision_counts.items())),
        "contracts": contracts,
    }
