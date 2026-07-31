"""Build deterministic Norwegian textile and sewing discovery queries."""
from __future__ import annotations

from opportunity_engine.discovery.norway_textile_keywords import (
    DOMAIN,
    build_norway_textile_keyword_queries,
)


def build_clothing_inventory_queries(*, country: str = "Norge") -> list[dict[str, str]]:
    """Return the bounded V1 pack with traceable signal components.

    The legacy function name is preserved for callers, while the returned domain
    now describes the expanded textile and sewing ecosystem.
    """
    return [
        {
            "domain": DOMAIN,
            "query_id": spec.query_id,
            "scenario": spec.scenario,
            "intent": spec.intent,
            "category": spec.category,
            "event_term": spec.event_term,
            "sector_term": spec.sector_term,
            "asset_term": spec.asset_term,
            "rotation_group": spec.rotation_group,
            "query": spec.query,
        }
        for spec in build_norway_textile_keyword_queries(country=country)
    ]
