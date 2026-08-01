#!/usr/bin/env python3
"""Run source-targeted Norway textile discovery with bounded page verification."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping

from opportunity_engine.discovery.auksjonen_current_category import (
    AuksjonenCurrentCategoryAugmentedProvider,
    AuksjonenCurrentCategoryCollector,
    AuksjonenCurrentCategoryConfig,
)
from opportunity_engine.discovery.auksjonen_playwright_fallback import (
    AuksjonenPlaywrightFallbackConfig,
    AuksjonenPlaywrightFallbackVerifier,
)
from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.clothing_inventory_search import (
    apply_post_verification_top5_hard_gate,
    run_clothing_inventory_discovery,
    verify_public_page,
    write_discovery_artifacts,
)
from opportunity_engine.discovery.early_opportunity_gate import (
    apply_early_opportunity_gate,
)
from opportunity_engine.discovery.norway_textile_source_targeted_queries import (
    NORWAY_TEXTILE_SOURCE_TARGETED_FRESHNESS,
    NORWAY_TEXTILE_SOURCE_TARGETED_QUERY_BUDGET,
    select_norway_textile_source_targeted_queries,
)
from opportunity_engine.discovery.norway_textile_verification_orchestration import (
    apply_norway_textile_page_verification_policy,
)
from opportunity_engine.discovery.source_channel_guard import (
    enforce_source_channel_identity,
)
from opportunity_engine.discovery.source_targeted_retrieval import (
    SourceTargetedSearchProvider,
)
from opportunity_engine.discovery.unified_opportunity_report import (
    write_unified_opportunity_report,
)


def _guarded_public_verifier(url: str):
    """Verify one public page and fail closed on generic source channels."""
    return enforce_source_channel_identity(verify_public_page(url))


def build_structured_discovery_queries(
    query_budget: int = NORWAY_TEXTILE_SOURCE_TARGETED_QUERY_BUDGET,
):
    """Return the approved Norway textile query set used by live discovery."""
    return select_norway_textile_source_targeted_queries(query_budget)


def collect_verification_failure_details(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Expose bounded verifier failures without weakening the final Hard Gate."""
    details: list[dict[str, Any]] = []
    candidates = result.get("all_discovered_candidates")
    if not isinstance(candidates, list):
        return details

    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        if candidate.get("post_verification_top5_block_reason") not in {
            "verification_failed",
            "norway_textile_page_verification_failed",
        }:
            continue
        verifications = candidate.get("verification")
        if not isinstance(verifications, list):
            continue
        for verification in verifications:
            if not isinstance(verification, Mapping):
                continue
            if verification.get("verified") is True:
                continue
            details.append({
                "title": candidate.get("title"),
                "url": verification.get("url") or (candidate.get("source_urls") or [None])[0],
                "error": verification.get("error"),
                "page_role": verification.get("page_role"),
                "listing_status": verification.get("listing_status"),
                "opportunity_identity": candidate.get("opportunity_identity"),
                "textile_category": candidate.get("textile_category"),
            })
    return details


def _disabled_playwright_diagnostics() -> dict[str, object]:
    return {
        "enabled": False,
        "scope": "specific_auksjonen_item_pages_only",
        "max_pages": 0,
        "attempted": 0,
        "succeeded": 0,
        "failed": 0,
        "budget_exhausted": 0,
        "attempted_urls": [],
        "successful_urls": [],
        "failed_urls": [],
        "errors": [],
        "used": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase_decision": False,
        "automatic_payment": False,
    }


def _disabled_current_category_diagnostics() -> dict[str, object]:
    return {
        "enabled": False,
        "scope": "one_approved_auksjonen_clothing_category",
        "category_url": None,
        "final_url": None,
        "pages_visited": 0,
        "rows_seen": 0,
        "specific_item_hits": 0,
        "item_urls": [],
        "errors": [],
        "used": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase_decision": False,
        "automatic_payment": False,
    }


def _write_fallback_persistence_error(
    output_dir: Path,
    report_path: Path,
    exc: Exception,
) -> Path:
    """Write an error artifact when persistence cannot initialize its own helper."""
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
        default="artifacts/norway-textile-discovery",
        help="Artifact directory",
    )
    parser.add_argument(
        "--persist-unified",
        action="store_true",
        help=(
            "After writing all JSON artifacts, copy unified-opportunity-report.json "
            "into SQLite through the canonical repository"
        ),
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get(
            "OPPORTUNITY_DATABASE_URL",
            "sqlite:///data/opportunity_engine.db",
        ),
        help="Database URL used only with --persist-unified",
    )
    parser.add_argument(
        "--alembic-config",
        default="alembic.ini",
        help="Alembic configuration used only with --persist-unified",
    )
    parser.add_argument("--results-per-query", type=int, default=10)
    parser.add_argument(
        "--query-budget",
        type=int,
        default=NORWAY_TEXTILE_SOURCE_TARGETED_QUERY_BUDGET,
        help="Number of source-diverse Norway textile queries to execute (1-16)",
    )
    parser.add_argument(
        "--freshness",
        choices=("none", "pd", "pw", "pm", "py"),
        default=NORWAY_TEXTILE_SOURCE_TARGETED_FRESHNESS,
        help="Brave page-age filter; 'none' avoids hiding still-active indexed sales",
    )
    parser.add_argument(
        "--verify-pages",
        action="store_true",
        help="Read the public HTTPS pages of the highest-ranked candidates",
    )
    parser.add_argument("--verification-limit", type=int, default=20)
    parser.add_argument(
        "--playwright-fallback",
        action="store_true",
        help=(
            "Render only specific Auksjonen item pages when the normal verifier "
            "returns insufficient public listing content"
        ),
    )
    parser.add_argument(
        "--playwright-limit",
        type=int,
        default=3,
        help="Maximum Auksjonen item pages rendered by Chromium (1-3)",
    )
    parser.add_argument(
        "--playwright-delay-seconds",
        type=float,
        default=2.5,
        help="Minimum delay after each bounded browser navigation",
    )
    parser.add_argument(
        "--auksjonen-current-category",
        action="store_true",
        help=(
            "Supplement Brave with specific item links from one approved public "
            "Auksjonen clothing/workwear category page"
        ),
    )
    parser.add_argument(
        "--auksjonen-current-limit",
        type=int,
        default=10,
        help="Maximum current Auksjonen item links added from the category (1-10)",
    )
    args = parser.parse_args()

    if not 1 <= args.results_per_query <= 20:
        raise SystemExit("--results-per-query must be between 1 and 20")
    if args.playwright_fallback and not args.verify_pages:
        raise SystemExit("--playwright-fallback requires --verify-pages")
    if args.auksjonen_current_category and not args.verify_pages:
        raise SystemExit("--auksjonen-current-category requires --verify-pages")
    if args.persist_unified and not str(args.database_url).strip():
        raise SystemExit("--database-url must not be empty with --persist-unified")

    api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("BRAVE_SEARCH_API_KEY is required")

    discovery_queries = build_structured_discovery_queries(args.query_budget)
    brave_freshness = None if args.freshness == "none" else args.freshness
    brave = BraveSearchProvider(
        api_key,
        freshness=brave_freshness,
        extra_snippets=True,
        operators=True,
    )
    source_provider = SourceTargetedSearchProvider(
        brave,
        queries=discovery_queries,
        request_budget=len(discovery_queries),
    )
    provider = source_provider
    current_category_diagnostics = _disabled_current_category_diagnostics()

    if args.auksjonen_current_category:
        try:
            auksjonen_query = next(
                query for query in discovery_queries if query.query_id == "sale-03"
            )
        except StopIteration as exc:
            raise SystemExit(
                "--auksjonen-current-category requires the sale-03 query in the budget"
            ) from exc
        collection = AuksjonenCurrentCategoryCollector(
            AuksjonenCurrentCategoryConfig(
                max_listings=args.auksjonen_current_limit,
                delay_seconds=args.playwright_delay_seconds,
            )
        ).collect(query=auksjonen_query)
        current_category_diagnostics = collection.diagnostics()
        provider = AuksjonenCurrentCategoryAugmentedProvider(
            source_provider,
            target_query=auksjonen_query.query,
            current_hits=collection.hits,
        )

    playwright_verifier: AuksjonenPlaywrightFallbackVerifier | None = None
    verifier = None
    if args.verify_pages:
        if args.playwright_fallback:
            playwright_verifier = AuksjonenPlaywrightFallbackVerifier(
                _guarded_public_verifier,
                config=AuksjonenPlaywrightFallbackConfig(
                    max_pages=args.playwright_limit,
                    delay_seconds=args.playwright_delay_seconds,
                ),
            )
            verifier = playwright_verifier
        else:
            verifier = _guarded_public_verifier

    try:
        raw_result = run_clothing_inventory_discovery(
            provider,
            queries=discovery_queries,
            results_per_query=args.results_per_query,
            verifier=verifier,
            verification_limit=args.verification_limit,
        )
    finally:
        if playwright_verifier is not None:
            playwright_verifier.close()

    result = apply_early_opportunity_gate(raw_result)
    result = apply_post_verification_top5_hard_gate(result)
    result = apply_norway_textile_page_verification_policy(result)
    report = result["search_run_report"]
    diagnostics = source_provider.diagnostics()
    verification_failures = collect_verification_failure_details(result)
    playwright_diagnostics = (
        playwright_verifier.diagnostics()
        if playwright_verifier is not None
        else _disabled_playwright_diagnostics()
    )
    report["domain"] = "TEXTILE_AND_SEWING"
    report["market_code"] = "NO"
    report["taxonomy_aware_queries"] = True
    report["source_targeting_policy_applied"] = True
    report["source_targeting_query_budget"] = args.query_budget
    report["source_targeting_request_budget"] = len(discovery_queries)
    report["source_targeting_url_gate"] = diagnostics
    report["verification_failure_details"] = verification_failures
    report["verification_failure_detail_count"] = len(verification_failures)
    report["auksjonen_current_category_discovery"] = current_category_diagnostics
    report["auksjonen_playwright_fallback"] = playwright_diagnostics
    report["brave_freshness"] = args.freshness
    report["brave_extra_snippets"] = True
    report["brave_operators"] = True
    report["playwright_used"] = bool(
        playwright_diagnostics["used"] or current_category_diagnostics["used"]
    )

    output_dir = Path(args.output_dir)
    paths = write_discovery_artifacts(result, output_dir)
    unified_report_path = write_unified_opportunity_report(
        result,
        output_dir,
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
    print(f"Domain: {report['domain']}")
    print(f"Queries: {report['queries_submitted']}")
    print(f"Brave requests: {diagnostics['requests_made']}/{diagnostics['request_budget']}")
    print(f"Raw hits: {diagnostics['raw_hits']}")
    print(f"Accepted by URL gate: {diagnostics['accepted_hits']}")
    print(f"Rejected before classification: {diagnostics['rejected_hits']}")
    print(
        "Current Auksjonen category hits: "
        f"{current_category_diagnostics['specific_item_hits']}"
    )
    print(f"Playwright attempts: {playwright_diagnostics['attempted']}")
    print(f"Playwright successes: {playwright_diagnostics['succeeded']}")
    print(f"Verification failures detailed: {len(verification_failures)}")
    print(
        "Textile verification accepted: "
        f"{report['norway_textile_page_verification_accepted']}"
    )
    print(f"Top opportunities: {report['top5_count']}")
    for name, path in paths.items():
        print(f"{name}: {path}")

    if persistence_failure is not None:
        print(f"Unified persistence failed: {persistence_failure}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
