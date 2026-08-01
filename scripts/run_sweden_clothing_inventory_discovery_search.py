#!/usr/bin/env python3
"""Run the Sweden Clothing Inventory discovery pilot."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.clothing_inventory_search import (
    apply_post_verification_top5_hard_gate,
    run_clothing_inventory_discovery,
    write_discovery_artifacts,
)
from opportunity_engine.discovery.early_opportunity_gate import apply_early_opportunity_gate
from opportunity_engine.discovery.sweden_clothing_inventory import (
    SwedenLocalizedSearchProvider,
    build_sweden_clothing_inventory_queries,
    verify_sweden_public_page,
)
from opportunity_engine.discovery.sweden_psauction import (
    build_psauction_clothing_queries,
)
from opportunity_engine.discovery.sweden_psauction_playwright import (
    PSAuctionPlaywrightConfig,
    PSAuctionPlaywrightFallbackVerifier,
)
from opportunity_engine.discovery.sweden_psauction_prefetch import (
    PSAuctionPrefetchedSearchProvider,
)
from opportunity_engine.discovery.sweden_psauction_snippet_enrichment import (
    enrich_psauction_discovery_result,
)
from opportunity_engine.discovery.unified_opportunity_report import (
    write_unified_opportunity_report,
)
from opportunity_engine.markets.sweden import load_sweden_market_profile


ROOT = Path(__file__).resolve().parents[1]


def _write_fallback_persistence_error(
    output_dir: Path,
    report_path: Path,
    exc: Exception,
) -> Path:
    path = output_dir / "unified-persistence-error.json"
    path.write_text(
        json.dumps(
            {
                "status": "FAILED",
                "pipeline_name": "UNIFIED_DISCOVERY_PERSISTENCE_V1",
                "report_path": str(report_path),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "json_reports_remain_official": True,
                "report_deleted": False,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="artifacts/sweden-clothing-discovery",
        help="Artifact directory",
    )
    parser.add_argument("--results-per-query", type=int, default=10)
    parser.add_argument(
        "--source",
        choices=("open-web", "psauction"),
        default="open-web",
        help="Use the broad Swedish query pack or the bounded PS Auction source pack",
    )
    parser.add_argument(
        "--query-budget",
        type=int,
        default=None,
        help="Number of source-specific queries (default: open-web=16, psauction=8)",
    )
    parser.add_argument(
        "--freshness",
        choices=("none", "pd", "pw", "pm", "py"),
        default="pm",
        help="Brave page-age filter",
    )
    parser.add_argument(
        "--verify-pages",
        action="store_true",
        help="Read the public HTTPS pages of the highest-ranked candidates",
    )
    parser.add_argument("--verification-limit", type=int, default=20)
    parser.add_argument(
        "--psauction-browser-fallback",
        action="store_true",
        help="Render at most three exact PS Auction item pages after HTTP 403",
    )
    parser.add_argument(
        "--psauction-browser-pages",
        type=int,
        default=3,
        help="Maximum rendered PS Auction item pages (1-3)",
    )
    parser.add_argument(
        "--psauction-browser-delay-seconds",
        type=float,
        default=2.5,
    )
    parser.add_argument(
        "--persist-unified",
        action="store_true",
        help="Persist the completed unified report after JSON artifacts are written",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get(
            "OPPORTUNITY_DATABASE_URL",
            "sqlite:///data/opportunity_engine.db",
        ),
    )
    parser.add_argument("--alembic-config", default="alembic.ini")
    args = parser.parse_args()

    if not 1 <= args.results_per_query <= 20:
        raise SystemExit("--results-per-query must be between 1 and 20")
    if not 1 <= args.verification_limit <= 100:
        raise SystemExit("--verification-limit must be between 1 and 100")
    if args.psauction_browser_fallback and args.source != "psauction":
        raise SystemExit("--psauction-browser-fallback requires --source psauction")
    if args.psauction_browser_fallback and not args.verify_pages:
        raise SystemExit("--psauction-browser-fallback requires --verify-pages")
    if args.persist_unified and not str(args.database_url).strip():
        raise SystemExit("--database-url must not be empty with --persist-unified")

    api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("BRAVE_SEARCH_API_KEY is required")

    profile = load_sweden_market_profile(ROOT)
    brave = BraveSearchProvider(
        api_key,
        country=profile.market_code,
        freshness=None if args.freshness == "none" else args.freshness,
        extra_snippets=True,
        operators=True,
    )

    query_budget = args.query_budget
    if query_budget is None:
        query_budget = 8 if args.source == "psauction" else 16

    psauction_provider: PSAuctionPrefetchedSearchProvider | None = None
    if args.source == "psauction":
        queries = build_psauction_clothing_queries(query_budget)
        psauction_provider = PSAuctionPrefetchedSearchProvider(
            brave,
            queries=queries,
            request_budget=len(queries),
        )
        provider = SwedenLocalizedSearchProvider(psauction_provider)
        query_pack = "SWEDEN_PSAUCTION_CLOTHING_INVENTORY_V1"
    else:
        queries = build_sweden_clothing_inventory_queries(query_budget)
        provider = SwedenLocalizedSearchProvider(brave)
        query_pack = "SWEDEN_CLOTHING_INVENTORY_V1"

    verifier = verify_sweden_public_page if args.verify_pages else None
    browser_verifier: PSAuctionPlaywrightFallbackVerifier | None = None
    if args.psauction_browser_fallback:
        browser_verifier = PSAuctionPlaywrightFallbackVerifier(
            verify_sweden_public_page,
            config=PSAuctionPlaywrightConfig(
                max_pages=args.psauction_browser_pages,
                delay_seconds=args.psauction_browser_delay_seconds,
            ),
        )
        verifier = browser_verifier

    try:
        raw_result = run_clothing_inventory_discovery(
            provider,
            queries=queries,
            results_per_query=args.results_per_query,
            verifier=verifier,
            verification_limit=args.verification_limit,
        )
    finally:
        if browser_verifier is not None:
            browser_verifier.close()

    result = apply_early_opportunity_gate(raw_result)
    result = apply_post_verification_top5_hard_gate(result)
    source_diagnostics = psauction_provider.diagnostics() if psauction_provider else None
    if source_diagnostics is not None:
        result = enrich_psauction_discovery_result(
            result,
            source_diagnostics.get("accepted_samples") or (),
        )

    report = result["search_run_report"]
    report["domain"] = "CLOTHING_INVENTORY"
    report["market_code"] = profile.market_code
    report["market_name"] = profile.market_name
    report["currency"] = profile.currency_code
    report["language_codes"] = list(profile.language_codes)
    report["transaction_scope"] = profile.transaction_scope
    report["market_profile_id"] = profile.profile_id
    report["source_mode"] = args.source.upper().replace("-", "_")
    report["source_target"] = "psauction.se" if psauction_provider else None
    report["query_pack"] = query_pack
    report["query_budget"] = len(queries)
    report["brave_country"] = profile.market_code
    report["brave_freshness"] = args.freshness
    report["brave_extra_snippets"] = True
    report["brave_operators"] = True
    report["source_diagnostics"] = source_diagnostics
    report["source_page_verifier_diagnostics"] = (
        browser_verifier.diagnostics() if browser_verifier else None
    )
    report["currency_conversion_performed"] = False
    report["tax_calculation_performed"] = False
    report["customs_calculation_performed"] = False
    report["logistics_calculation_performed"] = False

    output_dir = Path(args.output_dir)
    paths = write_discovery_artifacts(result, output_dir)
    unified_report_path = write_unified_opportunity_report(
        result,
        output_dir,
        market_code=profile.market_code,
        currency=profile.currency_code,
        domain="CLOTHING_INVENTORY",
    )
    paths["unified_opportunity_report"] = unified_report_path

    persistence_failure: Exception | None = None
    if args.persist_unified:
        try:
            from opportunity_engine.persistence.live_unified_persistence import (
                persist_unified_report_with_artifacts,
            )

            _, persistence_summary_path = persist_unified_report_with_artifacts(
                unified_report_path,
                output_dir,
                database_url=args.database_url,
                config_path=args.alembic_config,
            )
            paths["unified_persistence_summary"] = persistence_summary_path
        except Exception as exc:
            persistence_failure = exc
            error_path = getattr(exc, "artifact_path", None)
            if not isinstance(error_path, Path):
                error_path = _write_fallback_persistence_error(
                    output_dir,
                    unified_report_path,
                    exc,
                )
            paths["unified_persistence_error"] = error_path

    print(f"Status: {report['status']}")
    print(f"Market: {profile.market_code} / {profile.market_name}")
    print(f"Currency: {profile.currency_code}")
    print(f"Source: {report['source_mode']}")
    print(f"Queries: {report['queries_submitted']}")
    print(f"Top opportunities: {report['top5_count']}")
    for name, path in paths.items():
        print(f"{name}: {path}")

    if persistence_failure is not None:
        print(f"Unified persistence failed: {persistence_failure}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
