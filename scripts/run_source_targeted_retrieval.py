#!/usr/bin/env python3
"""Run bounded source-targeted Norway textile retrieval validation."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.clothing_inventory_search import (
    apply_post_verification_top5_hard_gate,
    run_clothing_inventory_discovery,
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
from opportunity_engine.discovery.source_targeted_queries import (
    SOURCE_TARGETED_REFERENCE_QUERIES,
)
from opportunity_engine.discovery.source_targeted_retrieval import (
    SourceTargetedSearchProvider,
)

REQUIRED_REFERENCE_CASE = "axl-sport-og-fritid"


def _write_validation_summary(payload: dict, path: Path) -> None:
    diagnostics = payload["source_targeting"]
    recovered = diagnostics["reference_cases_recovered"]
    required_recovered = payload["required_reference_recovered"]
    advisory_recovered = payload["advisory_references_recovered"]
    lines = [
        "SOURCE-TARGETED NORWAY TEXTILE RETRIEVAL",
        "========================================",
        f"Status: {payload['validation_status']}",
        f"Domain: {payload['domain']}",
        f"Freshness: {payload['freshness']}",
        f"Discovery queries: {payload['discovery_queries_submitted']}",
        f"Reference queries: {payload['reference_queries_submitted']}",
        f"Brave requests: {diagnostics['requests_made']}/{diagnostics['request_budget']}",
        f"Raw hits: {diagnostics['raw_hits']}",
        f"Accepted by URL gate: {diagnostics['accepted_hits']}",
        f"Rejected before classification: {diagnostics['rejected_hits']}",
        f"References recovered: {len(recovered)}/{len(diagnostics['reference_cases'])}",
        f"Recovered references: {', '.join(recovered) if recovered else 'none'}",
        f"Required reference: {payload['required_reference_case']}",
        f"Required reference recovered: {'yes' if required_recovered else 'no'}",
        (
            "Advisory references recovered: "
            f"{', '.join(advisory_recovered) if advisory_recovered else 'none'}"
        ),
    ]
    if diagnostics["zero_raw_hits"]:
        lines.extend([
            "",
            "ZERO-HIT DIAGNOSIS",
            "------------------",
            "Brave returned zero web results before the URL gate ran.",
            "This is a retrieval/query-window failure, not a URL-gate rejection.",
        ])

    lines.extend(["", "PER-QUERY DIAGNOSTICS", "---------------------"])
    for item in diagnostics["query_diagnostics"]:
        error = f" error={item['error']}" if item["error"] else ""
        lines.append(
            f"{item['query_id']}: raw={item['raw_hits']} "
            f"accepted={item['accepted_hits']} rejected={item['rejected_hits']}{error}"
        )
    if not diagnostics["query_diagnostics"]:
        lines.append("none")

    lines.extend(["", "ACCEPTED HOSTS", "--------------"])
    for host, count in diagnostics["accepted_hosts"].items():
        lines.append(f"{host}: {count}")
    if not diagnostics["accepted_hosts"]:
        lines.append("none")

    lines.extend(["", "URL-GATE REJECTIONS", "-------------------"])
    for reason, count in diagnostics["rejection_reasons"].items():
        lines.append(f"{reason}: {count}")
    if not diagnostics["rejection_reasons"]:
        lines.append("none")

    lines.extend([
        "",
        "SAFETY",
        "------",
        "Retrieval only. Playwright was not used.",
        "No page was verified, no opportunity was approved for Analysis,",
        "and no contact, bid, purchase, or payment occurred.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="artifacts/source-targeted-retrieval",
        help="Artifact directory",
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
        help=(
            "Brave page-age filter. Default 'none' avoids hiding still-active "
            "sales whose pages were indexed more than 31 days ago."
        ),
    )
    parser.add_argument(
        "--skip-reference-checks",
        action="store_true",
        help="Do not spend the three bounded reference-recall requests",
    )
    args = parser.parse_args()

    if not 1 <= args.results_per_query <= 20:
        raise SystemExit("--results-per-query must be between 1 and 20")

    api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("BRAVE_SEARCH_API_KEY is required")

    discovery_queries = select_norway_textile_source_targeted_queries(
        args.query_budget
    )
    reference_queries = (
        ()
        if args.skip_reference_checks
        else SOURCE_TARGETED_REFERENCE_QUERIES
    )
    all_queries = (*discovery_queries, *reference_queries)
    request_budget = len(all_queries)
    brave_freshness = None if args.freshness == "none" else args.freshness

    brave = BraveSearchProvider(
        api_key,
        freshness=brave_freshness,
        extra_snippets=True,
        operators=True,
    )
    provider = SourceTargetedSearchProvider(
        brave,
        queries=all_queries,
        request_budget=request_budget,
    )

    raw_result = run_clothing_inventory_discovery(
        provider,
        queries=discovery_queries,
        results_per_query=args.results_per_query,
        verifier=None,
        verification_limit=0,
    )

    reference_errors: list[dict[str, str]] = []
    for query in reference_queries:
        try:
            provider.search(query.query, count=args.results_per_query)
        except Exception as exc:
            reference_errors.append({
                "query_id": query.query_id,
                "query": query.query,
                "error": str(exc),
            })

    result = apply_early_opportunity_gate(raw_result)
    result = apply_post_verification_top5_hard_gate(result)
    diagnostics = provider.diagnostics()
    recovered = set(diagnostics["reference_cases_recovered"])
    required_reference_recovered = REQUIRED_REFERENCE_CASE in recovered
    advisory_references_recovered = sorted(
        recovered - {REQUIRED_REFERENCE_CASE}
    )
    reference_validation_passed = (
        not reference_queries
        or (required_reference_recovered and not reference_errors)
    )
    validation_status = (
        "PASS"
        if result["search_run_report"]["execution_status"] != "FAIL"
        and not diagnostics["zero_raw_hits"]
        and reference_validation_passed
        else "FAIL"
    )

    report = result["search_run_report"]
    report.update({
        "domain": "TEXTILE_AND_SEWING",
        "market_code": "NO",
        "taxonomy_aware_queries": True,
        "source_targeting_policy_applied": True,
        "source_targeting_query_budget": args.query_budget,
        "source_targeting_request_budget": request_budget,
        "source_targeting_reference_checks": bool(reference_queries),
        "source_targeting_reference_validation_passed": reference_validation_passed,
        "source_targeting_required_reference_case": REQUIRED_REFERENCE_CASE,
        "source_targeting_required_reference_recovered": required_reference_recovered,
        "source_targeting_advisory_references_recovered": advisory_references_recovered,
        "source_targeting_reference_errors": reference_errors,
        "source_targeting_zero_raw_hits": diagnostics["zero_raw_hits"],
        "source_targeting_url_gate": diagnostics,
        "brave_freshness": args.freshness,
        "brave_extra_snippets": True,
        "brave_operators": True,
        "playwright_used": False,
    })

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_paths = write_discovery_artifacts(result, output_dir)

    validation_payload = {
        "schema_version": "source-targeted-norway-textile-retrieval-1.0",
        "domain": "TEXTILE_AND_SEWING",
        "market_code": "NO",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "validation_status": validation_status,
        "discovery_queries_submitted": len(discovery_queries),
        "reference_queries_submitted": len(reference_queries),
        "freshness": args.freshness,
        "results_per_query": args.results_per_query,
        "required_reference_case": REQUIRED_REFERENCE_CASE,
        "required_reference_recovered": required_reference_recovered,
        "advisory_references_recovered": advisory_references_recovered,
        "source_targeting": diagnostics,
        "reference_errors": reference_errors,
        "core_search_report": report,
        "automatic_contact": False,
        "automatic_purchase_decision": False,
        "page_verification_performed": False,
        "playwright_used": False,
        "analysis_engine_used": False,
    }
    validation_json = output_dir / "source-targeted-validation.json"
    validation_summary = output_dir / "source-targeted-validation-summary.txt"
    validation_json.write_text(
        json.dumps(validation_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_validation_summary(validation_payload, validation_summary)

    print(validation_summary.read_text(encoding="utf-8"))
    for name, path in artifact_paths.items():
        print(f"{name}: {path}")
    print(f"validation_json: {validation_json}")
    print(f"validation_summary: {validation_summary}")
    return 0 if validation_status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
