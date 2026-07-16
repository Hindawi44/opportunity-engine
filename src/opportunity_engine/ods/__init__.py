"""Opportunity Development System core package."""

from .discovery import FashionDiscoveryPlugin
from .discovery_framework import CuratedDiscoveryPlugin, OpportunitySeed, Scanner
from .models import (
    ODSRequest,
    ODSSession,
    OpportunityCandidate,
    Stage,
    StageResult,
    Status,
)
from .plugins import ODSPlugin, PluginRegistry
from .ranking import OpportunityRankingPlugin, RankedOpportunity, RankingWeights
from .workflow import DEFAULT_WORKFLOW, WorkflowEngine

__all__ = [
    "CuratedDiscoveryPlugin",
    "DEFAULT_WORKFLOW",
    "FashionDiscoveryPlugin",
    "ODSPlugin",
    "ODSRequest",
    "ODSSession",
    "OpportunityCandidate",
    "OpportunityRankingPlugin",
    "OpportunitySeed",
    "PluginRegistry",
    "RankedOpportunity",
    "RankingWeights",
    "Scanner",
    "Stage",
    "StageResult",
    "Status",
    "WorkflowEngine",
]
