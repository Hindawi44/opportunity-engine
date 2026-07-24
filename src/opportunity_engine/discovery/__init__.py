"""Discovery Engine V1 foundations."""

from opportunity_engine.discovery.classifier import classify_candidate, to_canonical_opportunity
from opportunity_engine.discovery.models import DiscoveryCandidate, DiscoveryResult
from opportunity_engine.discovery.opportunity_maps import CLOTHING_INVENTORY_MAP
from opportunity_engine.discovery.query_builder import build_clothing_inventory_queries

__all__ = [
    "CLOTHING_INVENTORY_MAP",
    "DiscoveryCandidate",
    "DiscoveryResult",
    "build_clothing_inventory_queries",
    "classify_candidate",
    "to_canonical_opportunity",
]
