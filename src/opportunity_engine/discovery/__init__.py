"""Discovery Engine V1 foundations."""

from opportunity_engine.discovery.classifier import classify_candidate, to_canonical_opportunity
from opportunity_engine.discovery.e2e_checkpoint import (
    CheckpointOutcome,
    EligibilityDecision,
    OpportunityDossier,
    build_opportunity_dossier,
    controlled_clothing_inventory_candidate,
    evaluate_analysis_eligibility,
    run_controlled_clothing_inventory_checkpoint,
)
from opportunity_engine.discovery.models import DiscoveryCandidate, DiscoveryResult
from opportunity_engine.discovery.opportunity_maps import CLOTHING_INVENTORY_MAP
from opportunity_engine.discovery.query_builder import build_clothing_inventory_queries

__all__ = [
    "CLOTHING_INVENTORY_MAP",
    "CheckpointOutcome",
    "DiscoveryCandidate",
    "DiscoveryResult",
    "EligibilityDecision",
    "OpportunityDossier",
    "build_clothing_inventory_queries",
    "build_opportunity_dossier",
    "classify_candidate",
    "controlled_clothing_inventory_candidate",
    "evaluate_analysis_eligibility",
    "run_controlled_clothing_inventory_checkpoint",
    "to_canonical_opportunity",
]
