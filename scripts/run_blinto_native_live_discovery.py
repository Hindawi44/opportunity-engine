#!/usr/bin/env python3
"""Run BLINTO_NATIVE_LIVE_DISCOVERY_V1 without Brave or another search engine."""
from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from opportunity_engine.discovery.blinto_historical_price_trust import (
    apply_blinto_historical_price_trust_gate,
)
from opportunity_engine.discovery.clothing_inventory_search import (
    PageVerification,
    apply_post_verification_top5_hard_gate,
    run_clothing_inventory_discovery,
    write_discovery_artifacts,
)
from opportunity_engine.discovery.early_opportunity_gate import apply_early_opportunity_gate
from opportunity_engine.discovery.sweden_blinto import enrich_blinto_discovery_result
from opportunity_engine.discovery.sweden_blinto_native_live import (
    BLINTO_NATIVE_LIVE_DISCOVERY_POLICY,
    BlintoNativeLiveSearchProvider,
    BlintoNativeLiveVerifier,
    FetchListing,
    build_blinto_native_live_queries,
)
from opportunity_engine.discovery.unified_opportunity_report import (
    write_unified_opportunity_report,
)
from opportunity_engine.markets.sweden import load_sweden_market_profile


def run_native_live_pipeline(
    *,
    output_dir: str | Path,
    results_per_query: int = 20,
    verification_limit: int = 20,
    fetch_listing: FetchListing | None = None,
    page_verifier: Callable[[str], PageVerification] | None = None,
) -> tuple[dict[str, Any], dict[str, Path]]:
    """Execute the native Blinto path and write standard Opportunity Engine artifacts."""
    provider = BlintoNativeLiveSearchProvider(fetch_listing=fetch_listing)
    verifier = BlintoNativeLiveVerifier(page_verifier) if page_verifier else BlintoNativeLiveVerifier()
    queries = build_blinto_native_live_queries()

    raw_result = run_clothing_inventory_discovery(
        provider,
        queries=queries,
        results_per_query=results_per_query,
        verifier=verifier,
        verification_limit=verification_limit,
    )
    result = apply_early_opportunity_gate(raw_result)
    result = apply_post_verification_top5_hard_gate(result)
    result = enrich_blinto_discovery_result(result)
    result = apply_blinto_historical_price_trust_gate(result)

    profile = load_sweden_market_profile(ROOT)
    report = result["search_run_report"]
    report["domain"] = "CLOTHING_INVENTORY"
    report["market_code"] = profile.market_code
    report["market_name"] = profile.market_name
    report["currency"] = profile.currency_code
    report["language_codes"] = list(profile.language_codes)
    report["transaction_scope"] = profile.transaction_scope
    report["market_profile_id"] = profile.profile_id
    report["source_mode"] = "BLINTO_NATIVE_LIVE"
    report["source_target"] = "blinto.se"
    report["query_pack"] = BLINTO_NATIVE_LIVE_DISCOVERY_POLICY
    report["query_budget"] = len(queries)
    report["source_status_verification_authoritative"] = True
    report["brave_requests"] = 0
    report["paid_search_used"] = False
    report["search_engine_used"] = False
    report["source_diagnostics"] = provider.diagnostics()
    report["source_page_verifier_diagnostics"] = verifier.diagnostics()
    report["currency_conversion_performed"] = False
    report["tax_calculation_performed"] = False
    report["customs_calculation_performed"] = False
    report["logistics_calculation_performed"] = False

    destination = Path(output_dir)
    paths = write_discovery_artifacts(result, destination)
    unified_report_path = write_unified_opportunity_report(
        result,
        destination,
        market_code=profile.market_code,
        currency=profile.currency_code,
        domain="CLOTHING_INVENTORY",
    )
    paths["unified_opportunity_report"] = unified_report_path
    return result, paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="artifacts/blinto-native-live-discovery-v1",
    )
    parser.add_argument("--results-per-query", type=int, default=20)
    parser.add_argument("--verification-limit", type=int, default=20)
    args = parser.parse_args()

    if not 1 <= args.results_per_query <= 20:
        raise SystemExit("--results-per-query must be between 1 and 20")
    if not 1 <= args.verification_limit <= 100:
        raise SystemExit("--verification-limit must be between 1 and 100")

    result, paths = run_native_live_pipeline(
        output_dir=args.output_dir,
        results_per_query=args.results_per_query,
        verification_limit=args.verification_limit,
    )
    report = result["search_run_report"]
    verifier = report.get("source_page_verifier_diagnostics") or {}
    source = report.get("source_diagnostics") or {}

    print(f"Policy: {BLINTO_NATIVE_LIVE_DISCOVERY_POLICY}")
    print(f"Status: {report.get('status')}")
    print(f"Source mode: {report.get('source_mode')}")
    print(f"Brave requests: {report.get('brave_requests')}")
    print(f"Listing requests: {source.get('listing_requests')}")
    print(f"Native clothing candidates: {source.get('accepted_hits')}")
    print(f"Exact page checks: {verifier.get('exact_page_verification_attempts')}")
    print(f"ACTIVE pages: {verifier.get('active_pages')}")
    print(f"Confirmed sales: {report.get('confirmed_sales')}")
    print(f"Top opportunities: {report.get('top5_count')}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
