"""Opportunity Development System core package."""

from .bdna import BDNAPlugin, BusinessBlueprint
from .brreg import BRREG_API_BASE, BRREG_ENTITY_MEDIA_TYPE, BrregClient, BrregConnector
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
    build_executive_decision,
)
from .discovery import FashionDiscoveryPlugin
from .discovery_framework import CuratedDiscoveryPlugin, OpportunitySeed, Scanner
from .evidence_weighting import EvidenceAdjustment, calculate_ssb_adjustment
from .financial import FinancialInputs, FinancialReport, FinancialScenario, build_financial_report
from .finn import (
    FINN_API_BASE,
    FINN_API_KEY_HEADER,
    FinnApiClient,
    FinnConnector,
    parse_finn_atom_feed,
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
from .models import ODSRequest, ODSSession, OpportunityCandidate, Stage, StageResult, Status
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
from .validation import ValidationExperiment, ValidationPlugin, ValidationReport
from .workflow import DEFAULT_WORKFLOW, WorkflowEngine

__all__ = [
    "BDNAPlugin", "BRREG_API_BASE", "BRREG_ENTITY_MEDIA_TYPE", "BrregClient",
    "BrregConnector", "BrregEvidenceSummary", "BusinessBlueprint",
    "ConnectorRegistry", "ConnectorScanStatus", "CuratedDiscoveryPlugin",
    "DEFAULT_EXTRACTION_RULES", "DEFAULT_WORKFLOW", "DataConnector",
    "DecisionInputs", "EvidenceAdjustment", "ExecutiveDecision",
    "ExecutiveDecisionReport", "ExtractionRule", "FINN_API_BASE",
    "FINN_API_KEY_HEADER", "FashionDiscoveryPlugin", "FinancialInputs",
    "FinancialReport", "FinancialScenario", "FinnApiClient", "FinnConnector",
    "LiveDataPipeline", "LiveDataResult", "MemoryRunResult", "ODSAnalysisResult",
    "ODSPlugin", "ODSRequest", "ODSSession", "OpportunityCandidate",
    "OpportunityChange", "OpportunityChangeType", "OpportunityConfidence",
    "OpportunityExtractor", "OpportunityMemoryEngine", "OpportunityMemoryRecord",
    "OpportunityRankingPlugin", "OpportunitySeed", "PluginRegistry",
    "RankedOpportunity", "RankingWeights", "SSB_API_BASE",
    "SSB_RETAIL_TABLE_ID", "SSB_RETAIL_TABLE_URL", "SSBClient", "SSBConnector",
    "SSBMarketEvidence", "SSBMarketEvidenceService", "SSBTrendIntelligenceService",
    "SSBTrendSignal", "ScanSnapshot", "Scanner", "SourceDocument", "Stage",
    "StageResult", "StaticDataConnector", "Status", "TrendAdjustment",
    "USABLE_ALPHA_WORKFLOW", "UniversalOpportunityScanner", "ValidationExperiment",
    "ValidationPlugin", "ValidationReport", "WorkflowEngine", "analyze_json_stat2",
    "analyze_series", "build_alpha_engine", "build_executive_decision",
    "build_financial_report", "calculate_opportunity_confidence",
    "calculate_ssb_adjustment", "calculate_trend_adjustment", "parse_finn_atom_feed",
    "run_ods", "summarize_brreg_entities", "track_workflow_opportunities",
]
