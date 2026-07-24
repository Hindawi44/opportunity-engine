#!/usr/bin/env python3
"""Run the live Discovery Engine pilot against Brave Search."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.live_search import run_live_discovery
from opportunity_engine.discovery.query_builder import build_clothing_inventory_queries


def _top_results(report: dict[str, Any], *, limit: int = 10) -> list[dict[str, Any]]:
    classified = report.get("classified_results")
    classified = classified if isinstance(classified, list) else []
    priority = {"SALE_CONFIRMED": 0, "CONTACT_REQUIRED": 1, "REJECTED": 2}
    valid = [item for item in classified if isinstance(item, dict)]
    valid.sort(key=lambda item: priority.get(str(item.get("status")), 3))
    return valid[:limit]


def build_mobile_report(report: dict[str, Any], *, limit: int = 10) -> str:
    """Build a compact plain-text report readable on a phone."""
    errors = report.get("errors") if isinstance(report.get("errors"), list) else []
    lines = [
        "========================================",
        "DISCOVERY REPORT — PHONE VIEW",
        "========================================",
        f"Topic: {report.get('pilot_topic', 'UNKNOWN')}",
        f"Provider: {report.get('provider', 'UNKNOWN')}",
        f"Status: {report.get('status', 'UNKNOWN')}",
        "",
        f"Queries submitted: {report.get('queries_submitted', 0)}",
        f"Hits received: {report.get('hits_received', 0)}",
        f"Duplicates removed: {report.get('duplicates_removed', 0)}",
        f"Filtered out: {report.get('filtered_out_count', 0)}",
        f"Candidates received: {report.get('candidates_received', 0)}",
        f"Confirmed sales: {report.get('confirmed_sales', 0)}",
        f"Needs contact: {report.get('follow_up_leads', 0)}",
        f"Rejected after filter: {report.get('rejected_results', 0)}",
        f"Errors: {len(errors)}",
        "",
        "TOP RESULTS",
        "----------------------------------------",
    ]

    top = _top_results(report, limit=limit)
    if not top:
        lines.append("No results to display.")
    else:
        for index, item in enumerate(top, start=1):
            candidate = item.get("candidate") if isinstance(item.get("candidate"), dict) else {}
            title = str(candidate.get("title") or "Untitled").strip()
            url = str(candidate.get("url") or "").strip()
            status = str(item.get("status") or "UNKNOWN")
            scenario = str(item.get("scenario") or "UNKNOWN")
            lines.extend([
                f"{index}. [{status}] {title}",
                f"   Scenario: {scenario}",
                f"   URL: {url or 'Unavailable'}",
            ])

    if errors:
        lines.extend(["", "FIRST ERRORS", "----------------------------------------"])
        for index, item in enumerate(errors[:5], start=1):
            if not isinstance(item, dict):
                continue
            lines.append(f"{index}. Query: {item.get('query', 'UNKNOWN')}")
            lines.append(f"   Error: {item.get('error', 'UNKNOWN')}")

    lines.extend([
        "",
        "Automatic purchase decision: NO",
        "========================================",
    ])
    return "\n".join(lines)


def write_github_step_summary(text: str) -> None:
    """Append a readable report to the GitHub Actions job summary when available."""
    target = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if not target:
        return
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write("## Discovery Report — Phone View\n\n")
        handle.write("```text\n")
        handle.write(text)
        handle.write("\n```\n")


def write_reports(
    report: dict[str, Any],
    mobile_report: str,
    *,
    json_path: Path,
    text_path: Path,
) -> None:
    """Persist both the full machine report and a phone-friendly text report."""
    json_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    text_path.write_text(mobile_report + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="artifacts/discovery-v1.5-live-report.json")
    parser.add_argument("--text-report", default="artifacts/discovery-v1.5-phone-report.txt")
    parser.add_argument("--country", default="Norge")
    parser.add_argument("--results-per-query", type=int, default=10)
    parser.add_argument("--mobile-limit", type=int, default=10)
    parser.add_argument("--query-delay-seconds", type=float, default=1.1)
    args = parser.parse_args()

    api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("BRAVE_SEARCH_API_KEY is required")

    query_records = build_clothing_inventory_queries(country=args.country)
    queries = [item["query"] for item in query_records]
    provider = BraveSearchProvider(api_key=api_key)
    report = run_live_discovery(
        queries,
        provider,
        results_per_query=args.results_per_query,
        query_delay_seconds=args.query_delay_seconds,
    )
    report["pilot_version"] = "1.5"
    report["pilot_topic"] = "CLOTHING_INVENTORY"
    report["query_records"] = query_records
    report["live_network_used"] = True
    report["automatic_purchase_decision"] = False

    mobile_report = build_mobile_report(report, limit=max(1, args.mobile_limit))
    write_reports(
        report,
        mobile_report,
        json_path=Path(args.report),
        text_path=Path(args.text_report),
    )
    print(mobile_report)
    write_github_step_summary(mobile_report)
    return 0 if report["status"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
