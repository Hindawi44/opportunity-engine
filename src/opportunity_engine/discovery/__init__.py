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
from opportunity_engine.discovery.norway_textile_keywords import (
    DOMAIN as NORWAY_TEXTILE_KEYWORD_DOMAIN,
    SCHEMA_VERSION as NORWAY_TEXTILE_KEYWORD_SCHEMA_VERSION,
    NorwayTextileKeywordQuery,
    build_norway_textile_keyword_queries,
)
from opportunity_engine.discovery.opportunity_maps import CLOTHING_INVENTORY_MAP
from opportunity_engine.discovery.query_builder import build_clothing_inventory_queries
from opportunity_engine.discovery.textile_taxonomy import (
    SCHEMA_VERSION as TEXTILE_TAXONOMY_SCHEMA_VERSION,
    OpportunityCategory,
    TaxonomyDecision,
    build_textile_taxonomy_audit,
    classify_textile_opportunity,
)
from opportunity_engine.discovery.unified_opportunity_contract import (
    SCHEMA_VERSION as UNIFIED_OPPORTUNITY_CONTRACT_SCHEMA_VERSION,
    UnifiedOpportunityContractError,
    UnifiedOpportunityContractV1,
)
from opportunity_engine.discovery.openai_strict_schema_compat import (
    install_openai_hunt_case_schema_compat,
)

install_openai_hunt_case_schema_compat()

__all__ = [
    "CLOTHING_INVENTORY_MAP",
    "CheckpointOutcome",
    "DiscoveryCandidate",
    "DiscoveryResult",
    "EligibilityDecision",
    "NORWAY_TEXTILE_KEYWORD_DOMAIN",
    "NORWAY_TEXTILE_KEYWORD_SCHEMA_VERSION",
    "NorwayTextileKeywordQuery",
    "OpportunityCategory",
    "OpportunityDossier",
    "TEXTILE_TAXONOMY_SCHEMA_VERSION",
    "TaxonomyDecision",
    "UNIFIED_OPPORTUNITY_CONTRACT_SCHEMA_VERSION",
    "UnifiedOpportunityContractError",
    "UnifiedOpportunityContractV1",
    "build_clothing_inventory_queries",
    "build_norway_textile_keyword_queries",
    "build_opportunity_dossier",
    "build_textile_taxonomy_audit",
    "classify_candidate",
    "classify_textile_opportunity",
    "controlled_clothing_inventory_candidate",
    "evaluate_analysis_eligibility",
    "run_controlled_clothing_inventory_checkpoint",
    "to_canonical_opportunity",
]
