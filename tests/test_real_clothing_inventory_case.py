from opportunity_engine.discovery.real_case import (
    REAL_CASE_SOURCE_URL,
    run_real_clothing_inventory_case,
)


def test_real_case_preserves_public_source_and_classifies_auction() -> None:
    outcome = run_real_clothing_inventory_case()

    assert outcome.discovery_result.scenario == "AUCTION"
    assert outcome.discovery_result.status == "SALE_CONFIRMED"
    assert outcome.dossier.confirmed_facts["source_url"] == REAL_CASE_SOURCE_URL
    assert outcome.dossier.confirmed_facts["source_name"] == "AUKSJONEN_NO_PUBLIC_LISTING"
    assert outcome.dossier.confirmed_facts["location"] == "SEM"


def test_real_case_preserves_seller_claims_and_missing_evidence() -> None:
    outcome = run_real_clothing_inventory_case()
    dossier = outcome.dossier

    assert dossier.seller_claims["quantity"] == 310
    assert dossier.seller_claims["asking_price_nok"] == 200
    assert "public_contact" in dossier.unknown_fields
    assert "market comparable evidence" in dossier.missing_evidence
    assert outcome.eligibility.eligible_for_analysis is False
    assert "verified market comparables" in outcome.eligibility.missing_requirements


def test_real_case_reaches_honest_evidence_required_without_action() -> None:
    outcome = run_real_clothing_inventory_case()

    assert outcome.outcome_type == "EVIDENCE_REQUIRED"
    assert outcome.analysis_invoked is False
    assert outcome.automatic_purchase_decision is False
    assert outcome.canonical_opportunity is not None
    assert outcome.canonical_opportunity["source"]["asking_price_nok"] == 200
    assert outcome.canonical_opportunity["discovery_data"]["quantity"] == 310
