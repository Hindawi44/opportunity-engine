#!/usr/bin/env python3
"""Run the bounded FINN indexed-listing rescue retrieval test."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.finn_indexed_rescue import (
    FINN_INDEXED_RESCUE_FRESHNESS,
    run_finn_indexed_retrieval,
)
from opportunity_engine.discovery.finn_indexed_rescue_queries import (
    FINN_INDEXED_BROAD_RESCUE_QUERIES,
)


def _write_summary(report: dict, path: Path) -> None:
    recovered = report["reference_items_recovered"]
    lines = [
        "FINN INDEXED LISTING RESCUE",
        "============================",
        f"Status: {'PASS' if report['rescue_success'] else 'FAIL'}",
        f"Queries: {report['queries_submitted']}",
        f"Raw hits: {report['hits_received']}",
        f"Unique FINN item URLs: {report['unique_finn_item_urls']}",
        f"Retrieval-eligible clothing lots: {report['retrieval_eligible_items']}",
        f"Required clothing lots: {report['minimum_specific_items']}",
        f"Reference items recovered: {len(recovered)}/{len(report['reference_item_ids'])}",
        f"Required reference items: {report['minimum_reference_items']}",
        f"Recovered reference IDs: {', '.join(recovered) if recovered else 'none'}",
        f"Provider errors: {len(report['errors'])}",
        "",
        "This is retrieval only. No page was verified and no item is approved for",
        "analysis, contact, bidding, purchase, or payment.",
        "",
        "TOP RETRIEVED ITEMS",
        "-------------------",
    ]
    for item in report["items"][:10]:
        marker = "KEEP" if item["retrieval_eligible"] else "DROP"
        lines.extend([
            f"[{marker}] {item['title']}",
            f"ID: {item['item_id']}",
            f"Quantity signal: {item['explicit_quantity']}",
            f"URL: {item['url']}",
            f"Queries: {', '.join(item['found_by_queries'])}",
            f"Classifier: {item['existing_classifier_state']}",
            "",
        ])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="artifacts/finn-indexed-rescue",
        help="Artifact directory",
    )
    parser.add_argument("--results-per-query", type=int, default=20)
    parser.add_argument("--minimum-specific-items", type=int, default=5)
    parser.add_argument("--minimum-reference-items", type=int, default=2)
    parser.add_argument(
        "--freshness",
        choices=("pd", "pw", "pm", "py"),
        default=FINN_INDEXED_RESCUE_FRESHNESS,
    )
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
    report = run_finn_indexed_retrieval(
        provider,
        queries=FINN_INDEXED_BROAD_RESCUE_QUERIES,
        results_per_query=args.results_per_query,
        minimum_specific_items=args.minimum_specific_items,
        minimum_reference_items=args.minimum_reference_items,
    )
    report["executed_at"] = datetime.now(timezone.utc).isoformat()
    report["brave_freshness"] = args.freshness
    report["brave_extra_snippets"] = True
    report["brave_operators"] = True

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "finn-indexed-rescue-report.json"
    summary_path = output_dir / "finn-indexed-rescue-summary.txt"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_summary(report, summary_path)
    print(summary_path.read_text(encoding="utf-8"))
    print(f"JSON: {json_path}")
    return 0 if report["rescue_success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
