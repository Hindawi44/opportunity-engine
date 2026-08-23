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
from opportunity_engine.discovery.bridal_english_market_search import (
    install_bilingual_bridal_search,
)
from opportunity_engine.discovery.bridal_term_boundary_cleanup import (
    install_bridal_term_boundary_cleanup,
)
from opportunity_engine.discovery.bridal_identity_purity_cleanup import (
    install_bridal_identity_purity_cleanup,
)
from opportunity_engine.discovery.bridal_event_purity_cleanup import (
    install_bridal_event_purity_cleanup,
)
from opportunity_engine.discovery.stockhurt_redirect_partial_recovery import (
    install_stockhurt_redirect_partial_recovery,
)
from opportunity_engine.discovery.stockhurt_sale_mode_brand_cleanup import (
    install_stockhurt_sale_mode_brand_cleanup,
)
from opportunity_engine.discovery.unified_decision_priority import (
    install_unified_decision_priority,
)
from opportunity_engine.discovery.one_decision_consistency import (
    install_one_decision_consistency,
)
from opportunity_engine.discovery.central_intelligence_orchestrator_cli_hook import (
    install_central_intelligence_orchestrator_cli_hook,
)
from opportunity_engine.discovery.market_comparables_benchmark_cli_hook import (
    install_market_comparables_benchmark_cli_hook,
)
from opportunity_engine.discovery.market_comparables_brand_cleanup import (
    install_market_comparables_brand_cleanup,
)
from opportunity_engine.discovery.mathematical_logic_shadow_cli_hook import (
    install_mathematical_logic_shadow_cli_hook,
)
from opportunity_engine.discovery.learning_layer_review_cli_hook import (
    install_learning_layer_review_cli_hook,
)
from opportunity_engine.discovery.daily_auto_miss_learning_cli_hook import (
    install_daily_auto_miss_learning_cli_hook,
)
from opportunity_engine.discovery.unified_market_intelligence_river_cli_hook import (
    install_unified_market_intelligence_river_cli_hook,
)
from opportunity_engine.discovery.automatic_query_gap_miss_scout_cli_hook import (
    install_automatic_query_gap_miss_scout_cli_hook,
)
from opportunity_engine.discovery.promoted_stocklear_cli_hook import (
    install_promoted_stocklear_cli_hook,
)
from opportunity_engine.discovery.openai_fabric_procurement_cli_hook import (
    install_openai_fabric_procurement_cli_hook,
)
from opportunity_engine.discovery.fabric_procurement_watch_cli_hook import (
    install_fabric_procurement_watch_cli_hook,
)
from opportunity_engine.discovery.scheduled_promoted_core_cli_hook import (
    install_scheduled_promoted_core_cli_hook,
)
from opportunity_engine.discovery.unified_six_market_runtime_cli_hook import (
    install_unified_six_market_runtime_cli_hook,
)

install_openai_hunt_case_schema_compat()
install_bilingual_bridal_search()
install_bridal_term_boundary_cleanup()
install_bridal_identity_purity_cleanup()
install_bridal_event_purity_cleanup()
install_stockhurt_redirect_partial_recovery()
install_stockhurt_sale_mode_brand_cleanup()
install_unified_decision_priority()
install_one_decision_consistency()
# This synchronous hook runs only for the real daily checkpoint CLI, before its
# source artifacts are consolidated. It is not an atexit handler.
install_scheduled_promoted_core_cli_hook()
install_central_intelligence_orchestrator_cli_hook()
install_market_comparables_benchmark_cli_hook()
install_market_comparables_brand_cleanup()
# Registered before the unified river because atexit handlers run LIFO: the
# river writes unified-market-cases.json first, then Math V1 observes it.
install_mathematical_logic_shadow_cli_hook()
# Registered before the daily learner and river. LIFO execution therefore runs
# river/capture first, daily learning second, then Learning Layer aggregation.
install_learning_layer_review_cli_hook()
# Also registered before the river: LIFO makes the river finish source
# verification + missed-opportunity capture first, then this learner consumes
# the newly durable miss memory in the same daily run.
install_daily_auto_miss_learning_cli_hook()
install_unified_market_intelligence_river_cli_hook()
# Registered after the river but before Stocklear. LIFO execution is therefore:
# Stocklear -> independent QUERY_GAP scout -> river/capture -> daily learner.
install_automatic_query_gap_miss_scout_cli_hook()
# Registered after the river because atexit handlers run LIFO: promoted
# Stocklear writes its production feed first, then the river consumes it.
install_promoted_stocklear_cli_hook()
install_openai_fabric_procurement_cli_hook()
install_fabric_procurement_watch_cli_hook()
# Registered last so the daily six-market authority is emitted first at atexit.
# It consumes only artifacts written synchronously by the daily checkpoint CLI;
# learning/shadow hooks remain advisory and do not override this authority.
install_unified_six_market_runtime_cli_hook()

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
