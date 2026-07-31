import json

import pytest

from opportunity_engine.discovery.e2e_checkpoint import (
    run_controlled_clothing_inventory_checkpoint,
)
from opportunity_engine.discovery.unified_opportunity_contract import (
    SCHEMA_VERSION,
    UnifiedOpportunityContractError,
    UnifiedOpportunityContractV1,
)


def test_checkpoint_adapts_to_unified_contract_without_changing_decision() -> None:
    outcome = run_controlled_clothing_inventory_checkpoint()

    contract = UnifiedOpportunityContractV1.from_checkpoint_outcome(outcome)
    payload = contract.to_dict()

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["opportunity_id"] == outcome.dossier.opportunity_id
    assert payload["market"] == "NO"
    assert payload["listing_status"] == "ACTIVE"
    assert payload["verification_status"] == "REQUIRES_VERIFICATION"
    assert payload["commercial_status"] == "WATCH"
    assert payload["workflow_status"] == "NEW"
    assert payload["final_decision"] == "NO_DECISION"
    assert payload["automatic_purchase_decision"] is False
    assert outcome.outcome_type == "EVIDENCE_REQUIRED"
    assert outcome.analysis_invoked is False


def test_checkpoint_adapter_preserves_unknowns_and_does_not_invent_costs() -> None:
    outcome = run_controlled_clothing_inventory_checkpoint()

    contract = UnifiedOpportunityContractV1.from_checkpoint_outcome(outcome)
    payload = contract.to_dict()

    assert "quantity" in payload["missing_information"]
    assert "asking_price_nok" in payload["missing_information"]
    assert payload["risk"]["unknown_fields"]
    assert payload["recommended_actions"] == list(outcome.dossier.seller_questions)
    assert payload["cost_estimate"]
    assert all(value is None for value in payload["cost_estimate"].values())


def test_unified_contract_is_json_serializable_and_returns_detached_data() -> None:
    outcome = run_controlled_clothing_inventory_checkpoint()
    contract = UnifiedOpportunityContractV1.from_checkpoint_outcome(outcome)

    payload = contract.to_dict()
    json.dumps(payload)
    payload["source"]["name"] = "CHANGED"

    assert contract.source["name"] == "CONTROLLED_FIXTURE"


def test_unified_contract_rejects_unsupported_status_values() -> None:
    with pytest.raises(UnifiedOpportunityContractError, match="unsupported listing_status"):
        UnifiedOpportunityContractV1(
            opportunity_id="opportunity-1",
            market="NO",
            source={"name": "SOURCE", "url": "https://example.invalid/listing"},
            identity={"source_listing_id": "listing-1"},
            listing_status="LIVE",
            verification_status="UNVERIFIED",
            commercial_status="NOT_ANALYZED",
            workflow_status="NEW",
            final_decision="NO_DECISION",
        )


def test_unified_contract_keeps_automatic_purchase_disabled() -> None:
    with pytest.raises(
        UnifiedOpportunityContractError,
        match="automatic_purchase_decision must remain false",
    ):
        UnifiedOpportunityContractV1(
            opportunity_id="opportunity-1",
            market="NO",
            source={"name": "SOURCE", "url": "https://example.invalid/listing"},
            identity={"source_listing_id": "listing-1"},
            listing_status="ACTIVE",
            verification_status="VERIFIED",
            commercial_status="QUALIFIED",
            workflow_status="NEW",
            final_decision="NO_DECISION",
            automatic_purchase_decision=True,
        )
