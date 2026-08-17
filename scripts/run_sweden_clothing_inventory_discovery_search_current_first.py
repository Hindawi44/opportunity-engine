#!/usr/bin/env python3
"""Run the existing Sweden discovery engine with current-first source adapters.

This wrapper changes only Blinto/Klaravik retrieval priority. The underlying
Sweden runner, lifecycle verification, budgets, persistence, and PS Auction path
remain unchanged.
"""
from __future__ import annotations

from scripts import run_sweden_clothing_inventory_discovery_search as base
from opportunity_engine.discovery.sweden_current_first import (
    BlintoCurrentFirstPrefetchedSearchProvider,
    KlaravikCurrentFirstPrefetchedSearchProvider,
    build_blinto_current_first_queries,
    build_klaravik_current_first_queries,
)


def main() -> int:
    base.build_blinto_clothing_queries = build_blinto_current_first_queries
    base.BlintoPrefetchedSearchProvider = BlintoCurrentFirstPrefetchedSearchProvider
    base.build_klaravik_clothing_queries = build_klaravik_current_first_queries
    base.KlaravikPrefetchedSearchProvider = KlaravikCurrentFirstPrefetchedSearchProvider
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
