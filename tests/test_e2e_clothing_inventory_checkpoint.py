from opportunity_engine.discovery.e2e_checkpoint import (
    run_controlled_clothing_inventory_checkpoint,
)


def test_controlled_checkpoint_reaches_honest_evidence_required_outcome() -> None:
    outcome = run_controlled_clothing_inventory_checkpoint()

    assert outcome.outcome_type == "EVIDENCE_REQUIRED"
    assert outcome.discovery_result.status == "SALE_CONFIRMED"
    assert outcome.discovery_result.scenario == "INVENTORY_LIQUIDATION"
    assert outcome.eligibility.eligible_for_analysis is False
    assert outcome.analysis_invoked is False
    assert outcome.automatic_purchase_decision is False


def test_controlled_checkpoint_preserves_unknowns_without_invention() -> None:
    outcome = run_controlled_clothing_inventory_checkpoint()
    dossier = outcome.dossier
    canonical = outcome.canonical_opportunity

    assert "quantity" in dossier.unknown_fields
    assert "asking_price_nok" in dossier.unknown_fields
    assert dossier.seller_claims == {}
    assert dossier.supported_inferences == ()
    assert canonical is not None
    assert canonical["discovery_data"]["quantity"] is None
    assert canonical["source"]["asking_price_nok"] is None
    assert canonical["automatic_purchase_decision"] is False


def test_controlled_checkpoint_keeps_traceability_and_seller_questions() -> None:
    outcome = run_controlled_clothing_inventory_checkpoint()
    dossier = outcome.dossier

    assert dossier.confirmed_facts["source_url"].startswith("https://")
    assert dossier.provenance["text"]["source"] == "CONTROLLED_FIXTURE"
    assert dossier.provenance["classification"]["signals"]
    assert len(dossier.seller_questions) >= 5
    assert "verified market comparables" in outcome.eligibility.missing_requirements
