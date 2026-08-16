#!/usr/bin/env python3
"""Run the Sweden Clothing Inventory discovery pilot."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from opportunity_engine.discovery.blinto_historical_price_trust import (
    apply_blinto_historical_price_trust_gate,
)
from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.clothing_inventory_search import (
    apply_post_verification_top5_hard_gate,
    run_clothing_inventory_discovery,
    write_discovery_artifacts,
)
from opportunity_engine.discovery.early_opportunity_gate import apply_early_opportunity_gate
from opportunity_engine.discovery.sweden_blinto import (
    BlintoPrefetchedSearchProvider,
    build_blinto_clothing_queries,
    enrich_blinto_discovery_result,
    verify_blinto_public_page,
)
from opportunity_engine.discovery.sweden_clothing_inventory import (
    SwedenLocalizedSearchProvider,
    build_sweden_clothing_inventory_queries,
    verify_sweden_public_page,
)
from opportunity_engine.discovery.sweden_klaravik import (
    KlaravikPrefetchedSearchProvider,
    build_klaravik_clothing_queries,
    verify_klaravik_public_page,
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
TARGETED_SOURCES = frozenset({"psauction", "klaravik", "blinto"})


def _effective_brave_freshness(source: str, requested: str) -> str:
    """Use exact-page status, not search-index age, for direct auction sources.

    Targeted Swedish source packs already restrict results to one source and then
    verify exact public item pages as ACTIVE/ENDED. Search-engine page age is not
    an authoritative auction-state signal and can suppress still-relevant indexed
    inventory pages before the source verifier gets a chance to inspect them.
    The broad open-web mode keeps the caller's freshness filter unchanged.
    """
    if source in TARGETED_SOURCES:
        return "none"
    return requested


class _PSAuctionUpstreamScopeVerifier(PSAuctionPlaywrightFallbackVerifier):
    """Let exact indexed search prove status after strict discovery proved scope.

    This bridge is used only by the PS Auction source path below. Candidates on
    that path have already passed PSAuctionPrefetchedSearchProvider's exact-item,
    clothing-title and bulk-inventory gates across the complete bounded prefetch.
    The parent verifier still filters indexed search results to the same item ID;
    therefore the second search only needs to corroborate ACTIVE/ENDED state.
    """

    @staticmethod
    def _scope_is_proven(hits) -> bool:
        # The parent calls this only after _same_item_hits() has kept the exact
        # requested item ID. Upstream scope was already proved by the strict
        # PS Auction prefetch gate, so one exact indexed hit is sufficient here.
        return bool(hits)

    def diagnostics(self) -> dict[str, object]:
        diagnostics = super().diagnostics()
        diagnostics["upstream_scope_bridge"] = "PSAUCTION_PREFETCH_STRICT_GATE"
        return diagnostics


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
        choices=("open-web", "psauction", "klaravik", "blinto"),
        default="open-web",
        help=(
            "Use the broad Swedish query pack or one bounded source pack "
            "(PS Auction, Klaravik or Blinto)"
        ),
    )
    parser.add_argument(
        "--query-budget",
        type=int,
        default=None,
        help=(
            "Number of source-specific queries "
            "(default: open-web=16, psauction=8, klaravik=8, blinto=8)"
        ),
    )
    parser.add_argument(
        "--freshness",
        choices=("none", "pd", "pw", "pm", "py"),
        default="pm",
        help=(
            "Brave page-age filter for open-web mode. Direct source packs ignore "
            "index age and use exact-page ACTIVE/ENDED verification instead."
        ),
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
        help=(
            "Explicitly request rendered verification for PS Auction. "
            "Verified PS Auction source runs enable it automatically."
        ),
    )
    parser.add_argument(
        "--psauction-browser-pages",
        type=int,
        default=6,
        help="Maximum rendered PS Auction item pages (1-6)",
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
    effective_freshness = _effective_brave_freshness(args.source, args.freshness)
    brave = BraveSearchProvider(
        api_key,
        country=profile.market_code,
        freshness=None if effective_freshness == "none" else effective_freshness,
        extra_snippets=True,
        operators=True,
    )

    query_budget = args.query_budget
    if query_budget is None:
        query_budget = 16 if args.source == "open-web" else 8

    psauction_provider: PSAuctionPrefetchedSearchProvider | None = None
    klaravik_provider: KlaravikPrefetchedSearchProvider | None = None
    blinto_provider: BlintoPrefetchedSearchProvider | None = None
    if args.source == "psauction":
        queries = build_psauction_clothing_queries(query_budget)
        psauction_provider = PSAuctionPrefetchedSearchProvider(
            brave,
            queries=queries,
            request_budget=len(queries),
        )
        provider = SwedenLocalizedSearchProvider(psauction_provider)
        query_pack = "SWEDEN_PSAUCTION_CLOTHING_INVENTORY_V1"
    elif args.source == "klaravik":
        queries = build_klaravik_clothing_queries(query_budget)
        klaravik_provider = KlaravikPrefetchedSearchProvider(
            brave,
            queries=queries,
            request_budget=len(queries),
        )
        provider = SwedenLocalizedSearchProvider(klaravik_provider)
        query_pack = "SWEDEN_KLARAVIK_CLOTHING_INVENTORY_V1"
    elif args.source == "blinto":
        queries = build_blinto_clothing_queries(query_budget)
        blinto_provider = BlintoPrefetchedSearchProvider(
            brave,
            queries=queries,
            request_budget=len(queries),
        )
        provider = SwedenLocalizedSearchProvider(blinto_provider)
        query_pack = "SWEDEN_BLINTO_CLOTHING_INVENTORY_V1"
    else:
        queries = build_sweden_clothing_inventory_queries(query_budget)
        provider = SwedenLocalizedSearchProvider(brave)
        query_pack = "SWEDEN_CLOTHING_INVENTORY_V1"

    verifier = None
    if args.verify_pages:
        verifier = {
            "klaravik": verify_klaravik_public_page,
            "blinto": verify_blinto_public_page,
        }.get(args.source, verify_sweden_public_page)

    # Run #175 proved that PS Auction discovery can find strong exact-item
    # clothing lots while the lightweight source-page reader receives only a
    # public JS shell. For verified PS Auction runs, rendered verification is
    # therefore part of the source contract rather than an optional manual
    # diagnostic. It remains bounded to exact public item URLs and fails closed.
    use_psauction_browser_fallback = (
        args.source == "psauction" and args.verify_pages
    ) or args.psauction_browser_fallback

    browser_verifier: PSAuctionPlaywrightFallbackVerifier | None = None
    if use_psauction_browser_fallback:
        # The strict prefetch provider has already proved clothing/bulk scope
        # before verification begins. The bridge prevents the exact status
        # search from needlessly proving that same scope a second time.
        browser_verifier = _PSAuctionUpstreamScopeVerifier(
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
    targeted_provider = psauction_provider or klaravik_provider or blinto_provider
    source_diagnostics = targeted_provider.diagnostics() if targeted_provider else None
    if psauction_provider is not None and source_diagnostics is not None:
        result = enrich_psauction_discovery_result(
            result,
            source_diagnostics.get("accepted_samples") or (),
        )
    if blinto_provider is not None:
        result = enrich_blinto_discovery_result(result)
        result = apply_blinto_historical_price_trust_gate(result)

    source_target = {
        "psauction": "psauction.se",
        "klaravik": "klaravik.se",
        "blinto": "blinto.se",
    }.get(args.source)

    report = result["search_run_report"]
    report["domain"] = "CLOTHING_INVENTORY"
    report["market_code"] = profile.market_code
    report["market_name"] = profile.market_name
    report["currency"] = profile.currency_code
    report["language_codes"] = list(profile.language_codes)
    report["transaction_scope"] = profile.transaction_scope
    report["market_profile_id"] = profile.profile_id
    report["source_mode"] = args.source.upper().replace("-", "_")
    report["source_target"] = source_target
    report["query_pack"] = query_pack
    report["query_budget"] = len(queries)
    report["brave_country"] = profile.market_code
    report["brave_freshness_requested"] = args.freshness
    report["brave_freshness"] = effective_freshness
    report["source_status_verification_authoritative"] = args.source in TARGETED_SOURCES
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
