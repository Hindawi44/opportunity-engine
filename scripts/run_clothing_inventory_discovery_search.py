#!/usr/bin/env python3
"""Run source-targeted structured Clothing Inventory Discovery manually."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

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
from opportunity_engine.discovery.source_channel_guard import (
    enforce_source_channel_identity,
)
from opportunity_engine.discovery.source_targeted_queries import (
    SOURCE_TARGETED_FRESHNESS,
    SOURCE_TARGETED_QUERY_BUDGET,
    select_source_targeted_queries,
)
from opportunity_engine.discovery.source_targeted_retrieval import (
    SourceTargetedSearchProvider,
)


def _guarded_public_verifier(url: str):
    """Verify one public page and fail closed on generic source channels."""
    return enforce_source_channel_identity(verify_public_page(url))


def build_structured_discovery_queries(query_budget: int = SOURCE_TARGETED_QUERY_BUDGET):
    """Return the approved source-diverse query set used by live discovery."""
    return select_source_targeted_queries(query_budget)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="artifacts/clothing-inventory-discovery",
        help="Artifact directory",
    )
    parser.add_argument("--results-per-query", type=int, default=10)
    parser.add_argument(
        "--query-budget",
        type=int,
        default=SOURCE_TARGETED_QUERY_BUDGET,
        help="Number of source-diverse discovery queries to execute (1-16)",
    )
    parser.add_argument(
        "--freshness",
        choices=("none", "pd", "pw", "pm", "py"),
        default=SOURCE_TARGETED_FRESHNESS,
        help="Brave page-age filter; 'none' avoids hiding still-active indexed sales",
    )
    parser.add_argument(
        "--verify-pages",
        action="store_true",
        help="Read the public HTTPS pages of the highest-ranked candidates",
    )
    parser.add_argument("--verification-limit", type=int, default=20)
    args = parser.parse_args()

    if not 1 <= args.results_per_query <= 20:
        raise SystemExit("--results-per-query must be between 1 and 20")

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
    provider = SourceTargetedSearchProvider(
        brave,
        queries=discovery_queries,
        request_budget=len(discovery_queries),
    )
    raw_result = run_clothing_inventory_discovery(
        provider,
        queries=discovery_queries,
        results_per_query=args.results_per_query,
        verifier=_guarded_public_verifier if args.verify_pages else None,
        verification_limit=args.verification_limit,
    )
    result = apply_early_opportunity_gate(raw_result)
    result = apply_post_verification_top5_hard_gate(result)
    report = result["search_run_report"]
    diagnostics = provider.diagnostics()
    report["source_targeting_policy_applied"] = True
    report["source_targeting_query_budget"] = args.query_budget
    report["source_targeting_request_budget"] = len(discovery_queries)
    report["source_targeting_url_gate"] = diagnostics
    report["brave_freshness"] = args.freshness
    report["brave_extra_snippets"] = True
    report["brave_operators"] = True
    report["playwright_used"] = False

    paths = write_discovery_artifacts(result, Path(args.output_dir))
    print(f"Status: {report['status']}")
    print(f"Queries: {report['queries_submitted']}")
    print(f"Brave requests: {diagnostics['requests_made']}/{diagnostics['request_budget']}")
    print(f"Raw hits: {diagnostics['raw_hits']}")
    print(f"Accepted by URL gate: {diagnostics['accepted_hits']}")
    print(f"Rejected before classification: {diagnostics['rejected_hits']}")
    print(f"Top opportunities: {report['top5_count']}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
