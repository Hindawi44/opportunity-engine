"""Opportunity Development System core package."""

from .bdna import BDNAPlugin, BusinessBlueprint
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
from .validation import ValidationExperiment, ValidationPlugin, ValidationReport
from .workflow import DEFAULT_WORKFLOW, WorkflowEngine

__all__ = [
    "BDNAPlugin", "BusinessBlueprint", "CuratedDiscoveryPlugin",
    "DEFAULT_EXTRACTION_RULES", "DEFAULT_WORKFLOW", "DataConnector",
    "EvidenceAdjustment", "ExtractionRule", "FashionDiscoveryPlugin",
    "LiveDataPipeline", "LiveDataResult", "ODSAnalysisResult", "ODSPlugin",
    "ODSRequest", "ODSSession", "OpportunityCandidate", "OpportunityExtractor",
    "OpportunityRankingPlugin", "OpportunitySeed", "PluginRegistry",
    "RankedOpportunity", "RankingWeights", "SSB_API_BASE",
    "SSB_RETAIL_TABLE_ID", "SSB_RETAIL_TABLE_URL", "SSBClient", "SSBConnector",
    "SSBMarketEvidence", "SSBMarketEvidenceService", "Scanner", "SourceDocument",
    "Stage", "StageResult", "StaticDataConnector", "Status",
    "USABLE_ALPHA_WORKFLOW", "ValidationExperiment", "ValidationPlugin",
    "ValidationReport", "WorkflowEngine", "build_alpha_engine",
    "calculate_ssb_adjustment", "run_ods",
]
