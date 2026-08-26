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
from opportunity_engine.discovery.ai_teaching_gate_cli_hook import (
    install_ai_teaching_gate_cli_hook,
)
from opportunity_engine.discovery.unified_learning_spine_cli_hook import (
    install_unified_learning_spine_cli_hook,
)
from opportunity_engine.discovery.daily_auto_miss_learning_cli_hook import (
    install_daily_auto_miss_learning_cli_hook,
)
from opportunity_engine.discovery.unified_market_intelligence_river_cli_hook import (
    install_unified_market_intelligence_river_cli_hook,
)
from opportunity_engine.discovery.unified_search_truth_reconciliation_cli_hook import (
    install_unified_search_truth_reconciliation_cli_hook,
)
from opportunity_engine.discovery.expansion_route_continuity_v1 import (
    install_expansion_route_continuity_v1,
)
from opportunity_engine.discovery.fair_proven_route_recovery_v1 import (
    install_fair_proven_route_recovery_v1,
)
from opportunity_engine.discovery.commercial_anchor_outcome_learning_cli_hook import (
    install_commercial_anchor_outcome_learning_cli_hook,
)
from opportunity_engine.discovery.unified_search_runtime_cli_hook import (
    install_unified_search_runtime_cli_hook,
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
# Registered before Spine, the daily learner and river. LIFO execution therefore
# runs river -> daily learning -> Spine -> AI Teaching Gate -> Learning Layer.
install_learning_layer_review_cli_hook()
# Registered before Spine. Because atexit handlers run LIFO, Spine first writes
# Memory V2 + Route Portfolio, then this gate routes only unresolved work toward
# future manual MIND FORGE teaching. It never calls AI itself.
install_ai_teaching_gate_cli_hook()
# Registered between Learning Layer/Teaching Gate and the daily learner. The
# spine therefore sees same-run river output and same-run learning memory, while
# Learning Layer remains the final operator-facing review plane.
install_unified_learning_spine_cli_hook()
# Also registered before the river: LIFO makes the river finish source
# verification + missed-opportunity capture first, then this learner consumes
# the newly durable miss memory in the same daily run.
install_daily_auto_miss_learning_cli_hook()
install_unified_market_intelligence_river_cli_hook()
# Registered before Unified Search Runtime so LIFO executes reconciliation after
# the runtime has written current six-market search truth. This corrects stale
# report labels only; it does not create a second search path.
install_unified_search_truth_reconciliation_cli_hook()
# Synchronously patch only persistence/route continuity before the existing
# runtime registers its atexit callback. No search request or runtime is added.
install_expansion_route_continuity_v1()
# Wrap the now-established recovery loader only when the remembered candidate
# pool exceeds the existing recovery slots. This keeps 12 recovery fetches and
# the 30-page global cap unchanged while rotating oversubscribed routes fairly.
install_fair_proven_route_recovery_v1()
# Registered immediately before Unified Search Runtime. LIFO therefore executes
# the existing six-market Exa runtime first, then this review-only learner consumes
# the persisted per-anchor outcomes. It adds no search request or runtime.
install_commercial_anchor_outcome_learning_cli_hook()
# Registered immediately after the river. LIFO lets the established fabric
# hooks write first, then this hook merges Exa FR/IT/NL and rewrites the unified
# operator search view before the river consumes final fabric truth.
install_unified_search_runtime_cli_hook()
# Registered after the river but before Stocklear. LIFO execution is therefore:
# Stocklear -> independent QUERY_GAP scout -> river/capture -> daily learner.
install_automatic_query_gap_miss_scout_cli_hook()
# Registered after the river because atexit handlers run LIFO: promoted
# Stocklear writes its production feed first, then the river consumes it.
install_promoted_stocklear_cli_hook()
install_openai_fabric_procurement_cli_hook()
install_fabric_procurement_watch_cli_hook()
# Registered last so the legacy six-market authority is emitted first at atexit.
# Unified Search Runtime later augments it with both project domains and removes
# the operational FR/IT/NL search gap without enabling automatic actions.
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
