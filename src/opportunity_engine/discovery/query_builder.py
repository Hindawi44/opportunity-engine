"""Build deterministic Norwegian search queries from opportunity scenarios."""
from __future__ import annotations

from opportunity_engine.discovery.opportunity_maps import CLOTHING_INVENTORY_MAP


def build_clothing_inventory_queries(*, country: str = "Norge") -> list[dict[str, str]]:
    """Return deduplicated queries with traceable scenario metadata."""
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for scenario, phrases in CLOTHING_INVENTORY_MAP.items():
        for phrase in phrases:
            query = f"{phrase} {country}".strip()
            normalized = " ".join(query.lower().split())
            if normalized in seen:
                continue
            seen.add(normalized)
            output.append({"domain": "CLOTHING_INVENTORY", "scenario": scenario, "query": query})
    return output
