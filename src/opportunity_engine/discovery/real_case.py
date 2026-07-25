"""Real public Clothing Inventory validation case.

This module preserves one publicly traceable Auksjonen.no candidate and runs it
through the merged Discovery -> Dossier -> Eligibility checkpoint. Missing
comparables and decision evidence remain explicit; no purchase action is made.
"""
from __future__ import annotations

from opportunity_engine.discovery.classifier import classify_candidate, to_canonical_opportunity
from opportunity_engine.discovery.e2e_checkpoint import (
    CheckpointOutcome,
    build_opportunity_dossier,
    evaluate_analysis_eligibility,
)
from opportunity_engine.discovery.models import DiscoveryCandidate


REAL_CASE_SOURCE_URL = "https://www.auksjonen.no/auksjoner/overskudd_klaer"


def real_clothing_inventory_candidate() -> DiscoveryCandidate:
    """Preserve one real public Auksjonen.no clothing-lot candidate."""
    return DiscoveryCandidate(
        title=(
            "310 stk Univern Hi-Vis Arbeidsjakker i flere størrelser – "
            "Flammehemmende & Antistatisk"
        ),
        url=REAL_CASE_SOURCE_URL,
        source="AUKSJONEN_NO_PUBLIC_LISTING",
        discovered_at="2026-07-25T12:30:00Z",
        text=(
            "Auksjonen.no Klær/Arbeidsklær listing. 310 stk Univern Hi-Vis "
            "arbeidsjakker i flere størrelser, flammehemmende og antistatisk. "
            "Auksjon avsluttet; offentlig side viste høyeste bud 200 NOK og sted SEM."
        ),
        location="SEM",
        quantity=310,
        price_nok=200,
        contact=None,
    )


def run_real_clothing_inventory_case() -> CheckpointOutcome:
    """Run the preserved real candidate through the merged checkpoint."""
    candidate = real_clothing_inventory_candidate()
    result = classify_candidate(candidate)
    dossier = build_opportunity_dossier(result)
    eligibility = evaluate_analysis_eligibility(result, dossier)
    canonical = to_canonical_opportunity(result)

    if eligibility.eligible_for_analysis:
        outcome_type = "ANALYSIS_READY"
        analysis_invoked = False
    else:
        outcome_type = "EVIDENCE_REQUIRED"
        analysis_invoked = False

    return CheckpointOutcome(
        outcome_type=outcome_type,
        discovery_result=result,
        dossier=dossier,
        eligibility=eligibility,
        canonical_opportunity=canonical,
        analysis_invoked=analysis_invoked,
        automatic_purchase_decision=False,
    )
