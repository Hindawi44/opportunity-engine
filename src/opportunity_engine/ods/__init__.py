"""Opportunity Development System core package."""

from .bdna import BDNAPlugin, BusinessBlueprint
from .brreg import BRREG_API_BASE, BRREG_ENTITY_MEDIA_TYPE, BrregClient, BrregConnector
from .confidence import (
    BrregEvidenceSummary,
    OpportunityConfidence,
    calculate_opportunity_confidence,
    summarize_brreg_entities,
)
from .discovery import FashionDiscoveryPlugin
from .discovery_framework import CuratedDiscoveryPlugin, OpportunitySeed, Scanner
from .evidence_weighting import EvidenceAdjustment, calculate_ssb_adjustment
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
from .models import ODSRequest, ODSSession, OpportunityCandidate, Stage, StageResult, Status
from .plugins import ODSPlugin, PluginRegistry
from .ranking import OpportunityRankingPlugin, RankedOpportunity, RankingWeights
from .runner import ODSAnalysisResult, USABLE_ALPHA_WORKFLOW, build_alpha_engine, run_ods
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
from .validation import ValidationExperiment, ValidationPlugin, ValidationReport
from .workflow import DEFAULT_WORKFLOW, WorkflowEngine

__all__ = [
    "BDNAPlugin", "BRREG_API_BASE", "BRREG_ENTITY_MEDIA_TYPE", "BrregClient",
    "BrregConnector", "BrregEvidenceSummary", "BusinessBlueprint",
    "CuratedDiscoveryPlugin", "DEFAULT_EXTRACTION_RULES", "DEFAULT_WORKFLOW",
    "DataConnector", "EvidenceAdjustment", "ExtractionRule", "FashionDiscoveryPlugin",
    "LiveDataPipeline", "LiveDataResult", "ODSAnalysisResult", "ODSPlugin",
    "ODSRequest", "ODSSession", "OpportunityCandidate", "OpportunityConfidence",
    "OpportunityExtractor", "OpportunityRankingPlugin", "OpportunitySeed",
    "PluginRegistry", "RankedOpportunity", "RankingWeights", "SSB_API_BASE",
    "SSB_RETAIL_TABLE_ID", "SSB_RETAIL_TABLE_URL", "SSBClient", "SSBConnector",
    "SSBMarketEvidence", "SSBMarketEvidenceService", "SSBTrendIntelligenceService",
    "SSBTrendSignal", "Scanner", "SourceDocument", "Stage", "StageResult",
    "StaticDataConnector", "Status", "TrendAdjustment", "USABLE_ALPHA_WORKFLOW",
    "ValidationExperiment", "ValidationPlugin", "ValidationReport", "WorkflowEngine",
    "analyze_json_stat2", "analyze_series", "build_alpha_engine",
    "calculate_opportunity_confidence", "calculate_ssb_adjustment",
    "calculate_trend_adjustment", "run_ods", "summarize_brreg_entities",
]
