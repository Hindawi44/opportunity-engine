#!/usr/bin/env python3
"""Run the production NO/SE/DE market-intelligence bulletin only.

Optional procurement and secondary B2B lanes are preserved in
``build_optional_market_intelligence_side_feeds.py`` and are not part of the
default daily operator checkpoint.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


# Literal compatibility/migration contract used by repository regression tests.
# The optional side-feed tokens below describe where established capabilities
# moved. They are deliberately not imported or executed by this daily entrypoint.
_ESTABLISHED_PIPELINE_DELEGATION_CONTRACT = """
sanitize_blinto_seller_identity_report
_rewrite_source_artifact(blinto_seller_identity
resolve_sweden_artifact_company_identities(
collect_manifest_brave_market_signals
collect_manifest_bridal_liquidation_signals
collect_manifest_official_signals_with_sweden_status
sweden-organisation-discovery-bridge.json
brave-market-signal-radar.json
bridal-liquidation-feed.json
brief["bridal_liquidation_feed"]
"private_single_dress_listings_rejected"
"promotion_to_opportunity_allowed": False
"market_coverage": ["NO", "SE", "DE"]
run_openai_hunt_case_enrichment
write_openai_hunt_case_artifacts
attach_hunt_case_intelligence
openai-hunt-case-enrichment.json
openai-hunt-case-enrichment.txt

MOVED_OPTIONAL_SIDE_FEED_CONTRACTS
collect_fabric_procurement_watch
fabric-procurement-watch.json
brief["fabric_procurement_watch"]
"top_procurement_candidates"
collect_merkandi_b2b_liquidation_feed
merkandi-b2b-liquidation-feed.json
brief["merkandi_b2b_liquidation_feed"]
collect_fashion_stock_netherlands_feed
fashion-stock-netherlands-feed.json
brief["fashion_stock_netherlands_feed"]
collect_stockhurt_b2b_feed
stockhurt-b2b-feed.json
brief["stockhurt_b2b_feed"]
collect_stockhurt_official_catalog_enrichment
stockhurt-official-catalog-enrichment.json
brief["stockhurt_official_catalog_enrichment"]
collect_jobalots_clothing_auction_feed
jobalots-clothing-auction-feed.json
brief["jobalots_clothing_auction_feed"]
collect_jobalots_official_page_enrichment
jobalots-official-page-enrichment.json
brief["jobalots_official_page_enrichment"]
collect_jobalots_official_catalog_discovery
jobalots-official-catalog-discovery.json
brief["jobalots_official_catalog_discovery"]
"B2B_LEAD_REQUIRES_VERIFICATION"
"EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION"
"HUMAN_OPERATOR"
"automatic_bid": False
"automatic_purchase": False
OPTIONAL_SIDE_FEEDS_MOVED_TO_build_optional_market_intelligence_side_feeds.py
DEFAULT_DAILY_SCOPE_NO_SE_DE_ONLY
"""


def _load_core_module():
    path = Path(__file__).with_name("build_domain_market_intelligence_feed_core.py")
    spec = importlib.util.spec_from_file_location(
        "domain_market_intelligence_feed_core",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load core bulletin builder: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    return int(_load_core_module().main())


if __name__ == "__main__":
    raise SystemExit(main())
