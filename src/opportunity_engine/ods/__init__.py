"""Opportunity Development System core package."""

from .auksjonen import (
    AUKSJONEN_BASE_URL,
    AUKSJONEN_LISTINGS_URL,
    AuksjonenClient,
    AuksjonenConnector,
    parse_auksjonen_listing_page,
)
from .bdna import BDNAPlugin, BusinessBlueprint
from .brreg import BRREG_API_BASE, BRREG_ENTITY_MEDIA_TYPE, BrregClient, BrregConnector
from .brreg_collector import (
    BrregCollectionResult,
    BrregOpportunityCollector,
    BrregSearchSlice,
)
from .confidence import (
    BrregEvidenceSummary,
    OpportunityConfidence,
    calculate_opportunity_confidence,
    summarize_brreg_entities,
)
from .decision import (
    DecisionInputs,
    ExecutiveDecision,
    ExecutiveDecisionReport,
    OpportunityDecisionResult,
    advance_decision_candidate,
    build_executive_decision,
    decide_opportunity,
)
from .decision_feedback import (
    DecisionFeedbackReport,
    DecisionOutcomeEvidence,
    DecisionRuleRecommendation,
    FeedbackDirection,
    build_decision_feedback,
)
from .decision_policy import (
    DecisionPolicyAuditEvent,
    DecisionPolicyProposal,
    DecisionPolicyReviewResult,
    PolicyReviewStatus,
    create_policy_proposal,
    review_policy_proposal,
)
from .decision_policy_release import (
    DecisionPolicyChangeSet,
    stage_approved_policy_change,
)
from .discovery import FashionDiscoveryPlugin
from .discovery_framework import CuratedDiscoveryPlugin, OpportunitySeed, Scanner
from .evidence_weighting import EvidenceAdjustment, calculate_ssb_adjustment
from .executive_workflow import ExecutiveWorkflowInputs, build_decision_from_analysis
from .financial import (
    FinancialAssessmentEvidence,
    FinancialInputs,
    FinancialReport,
    FinancialScenario,
    advance_financially_assessed,
    build_financial_report,
)
from .finn import (
    FINN_API_BASE,
    FINN_API_KEY_HEADER,
    FinnApiClient,
    FinnConnector,
    parse_finn_atom_feed,
)
from .live_brreg_pipeline import (
    BrregStatusOpportunityExtractor,
    LiveBrregAnalysis,
    run_live_brreg_analysis,
)
from .live_data import (
    DEFAULT_EXTRACTION_RULES,
    DataConnector,
    ExtractionRule,
    LiveDataPipeline,
    LiveDataResult,
    OpportunityExtractor,
    SourceDocument,
    StaticDataConnector,
)
from .memory import (
    MemoryRunResult,
    OpportunityChange,
    OpportunityChangeType,
    OpportunityMemoryEngine,
    OpportunityMemoryRecord,
)
from .models import (
    LifecycleState,
    ODSRequest,
    ODSSession,
    OpportunityCandidate,
    Stage,
    StageResult,
    Status,
    can_transition_lifecycle,
)
from .outcome_learning import (
    OutcomeLearning,
    OutcomeObservation,
    learn_from_outcome,
    record_outcome,
)
from .plugins import ODSPlugin, PluginRegistry
from .ranking import OpportunityRankingPlugin, RankedOpportunity, RankingWeights
from .runner import ODSAnalysisResult, USABLE_ALPHA_WORKFLOW, build_alpha_engine, run_ods
from .scanner import (
    ConnectorRegistry,
    ConnectorScanStatus,
    ScanSnapshot,
    UniversalOpportunityScanner,
)
from .ssb import SSB_API_BASE, SSBClient, SSBConnector
from .ssb_market import (
    SSB_RETAIL_TABLE_ID,
    SSB_RETAIL_TABLE_URL,
    SSBMarketEvidence,
    SSBMarketEvidenceService,
)
from .ssb_trends import (
    SSBTrendIntelligenceService,
    SSBTrendSignal,
    TrendAdjustment,
    analyze_json_stat2,
    analyze_series,
    calculate_trend_adjustment,
)
from .tracking import track_workflow_opportunities
from .unified_opportunity import UnifiedOpportunity, UnifiedOpportunityExtractor
from .validation import (
    ValidationExperiment,
    ValidationExperimentResult,
    ValidationPlugin,
    ValidationReport,
    validate_opportunity,
)
from .workflow import DEFAULT_WORKFLOW, WorkflowEngine

__all__ = [
    "AUKSJONEN_BASE_URL", "AUKSJONEN_LISTINGS_URL", "AuksjonenClient", "AuksjonenConnector",
    "BDNAPlugin", "BRREG_API_BASE", "BRREG_ENTITY_MEDIA_TYPE", "BrregClient",
    "BrregCollectionResult", "BrregConnector", "BrregEvidenceSummary",
    "BrregOpportunityCollector", "BrregSearchSlice", "BrregStatusOpportunityExtractor",
    "BusinessBlueprint", "ConnectorRegistry", "ConnectorScanStatus",
    "CuratedDiscoveryPlugin", "DEFAULT_EXTRACTION_RULES", "DEFAULT_WORKFLOW",
    "DataConnector", "DecisionFeedbackReport", "DecisionInputs", "DecisionOutcomeEvidence",
    "DecisionPolicyAuditEvent", "DecisionPolicyChangeSet", "DecisionPolicyProposal",
    "DecisionPolicyReviewResult", "DecisionRuleRecommendation", "EvidenceAdjustment",
    "ExecutiveDecision", "ExecutiveDecisionReport", "ExecutiveWorkflowInputs",
    "ExtractionRule", "FINN_API_BASE", "FINN_API_KEY_HEADER", "FashionDiscoveryPlugin",
    "FeedbackDirection", "FinancialAssessmentEvidence", "FinancialInputs",
    "FinancialReport", "FinancialScenario", "FinnApiClient", "FinnConnector",
    "LifecycleState", "LiveBrregAnalysis", "LiveDataPipeline", "LiveDataResult",
    "MemoryRunResult", "ODSAnalysisResult", "ODSPlugin", "ODSRequest", "ODSSession",
    "OpportunityCandidate", "OpportunityChange", "OpportunityChangeType",
    "OpportunityConfidence", "OpportunityDecisionResult", "OpportunityExtractor",
    "OpportunityMemoryEngine", "OpportunityMemoryRecord", "OpportunityRankingPlugin",
    "OpportunitySeed", "OutcomeLearning", "OutcomeObservation", "PluginRegistry",
    "PolicyReviewStatus", "RankedOpportunity", "RankingWeights", "SSB_API_BASE",
    "SSB_RETAIL_TABLE_ID", "SSB_RETAIL_TABLE_URL", "SSBClient", "SSBConnector",
    "SSBMarketEvidence", "SSBMarketEvidenceService", "SSBTrendIntelligenceService",
    "SSBTrendSignal", "ScanSnapshot", "Scanner", "SourceDocument", "Stage",
    "StageResult", "StaticDataConnector", "Status", "TrendAdjustment",
    "USABLE_ALPHA_WORKFLOW", "UnifiedOpportunity", "UnifiedOpportunityExtractor",
    "UniversalOpportunityScanner", "ValidationExperiment", "ValidationExperimentResult",
    "ValidationPlugin", "ValidationReport", "WorkflowEngine", "advance_decision_candidate",
    "advance_financially_assessed", "analyze_json_stat2", "analyze_series",
    "build_alpha_engine", "build_decision_feedback", "build_decision_from_analysis",
    "build_executive_decision", "build_financial_report", "calculate_opportunity_confidence",
    "calculate_ssb_adjustment", "calculate_trend_adjustment", "can_transition_lifecycle",
    "create_policy_proposal", "decide_opportunity", "learn_from_outcome",
    "parse_auksjonen_listing_page", "parse_finn_atom_feed", "record_outcome",
    "review_policy_proposal", "run_live_brreg_analysis", "run_ods",
    "stage_approved_policy_change", "summarize_brreg_entities",
    "track_workflow_opportunities", "validate_opportunity",
]
