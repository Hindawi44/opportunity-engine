#!/usr/bin/env python3
"""Run the structured Clothing Inventory Discovery search manually."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from opportunity_engine.discovery.brave_precision import (
    BRAVE_PRECISION_FRESHNESS,
    build_clothing_inventory_precision_queries,
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
from opportunity_engine.discovery.source_channel_guard import (
    enforce_source_channel_identity,
)


def _guarded_public_verifier(url: str):
    """Verify one public page and fail closed on generic source channels."""
    return enforce_source_channel_identity(verify_public_page(url))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="artifacts/clothing-inventory-discovery",
        help="Artifact directory",
    )
    parser.add_argument("--results-per-query", type=int, default=10)
    parser.add_argument(
        "--freshness",
        choices=("pd", "pw", "pm", "py"),
        default=BRAVE_PRECISION_FRESHNESS,
        help="Brave freshness window: day, week, month, or year",
    )
    parser.add_argument(
        "--verify-pages",
        action="store_true",
        help="Read the public HTTPS pages of the highest-ranked candidates",
    )
    parser.add_argument("--verification-limit", type=int, default=20)
    args = parser.parse_args()

    api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("BRAVE_SEARCH_API_KEY is required")

    provider = BraveSearchProvider(
        api_key,
        freshness=args.freshness,
        extra_snippets=True,
        operators=True,
    )
    raw_result = run_clothing_inventory_discovery(
        provider,
        queries=build_clothing_inventory_precision_queries(),
        results_per_query=args.results_per_query,
        verifier=_guarded_public_verifier if args.verify_pages else None,
        verification_limit=args.verification_limit,
    )
    result = apply_early_opportunity_gate(raw_result)
    result = apply_post_verification_top5_hard_gate(result)
    report = result["search_run_report"]
    report["brave_precision_policy_applied"] = True
    report["brave_freshness"] = args.freshness
    report["brave_extra_snippets"] = True
    report["brave_operators"] = True
    paths = write_discovery_artifacts(result, Path(args.output_dir))
    print(f"Status: {report['status']}")
    print(f"Queries: {report['queries_submitted']}")
    print(f"Hits: {report['hits_received']}")
    print(f"Top opportunities: {report['top5_count']}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
