#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.discovery.cross_source_scent_entity_gated_v1 import (
    collect_entity_gated_cross_source_scent_expansion_v2,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-requests", type=int, default=12)
    parser.add_argument("--results-per-query", type=int, default=8)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = collect_entity_gated_cross_source_scent_expansion_v2(
        max_requests=args.max_requests,
        results_per_query=args.results_per_query,
    )
    json_path = output_dir / "cross-source-scent-expansion-v2.json"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    lines = [
        "CROSS-SOURCE SCENT EXPANSION V2 + ENTITY SCENT QUALITY GATE V1",
        f"status: {report.get('status')}",
        f"requests_made: {report.get('requests_made', 0)}/{report.get('request_budget', 0)}",
        f"accepted_signals: {report.get('accepted_signal_count', 0)}",
        f"entity_clusters: {report.get('entity_cluster_count', 0)}",
        f"qualified_entity_scents: {report.get('strong_scent_count', 0)}",
        f"source_intelligence_filtered: {report.get('source_intelligence_count', 0)}",
        f"followed_entity_scents: {report.get('followed_scent_count', 0)}",
    ]
    for scent in (report.get("followed_scents") or [])[:8]:
        lines.append(
            f"- [{scent.get('market_code')}] score={scent.get('score')} "
            f"{scent.get('label')} | evidence={scent.get('evidence_count')} | "
            f"sources={scent.get('independent_source_count')} | "
            f"follow_up_new={scent.get('new_follow_up_signal_count')} | "
            f"{scent.get('source_url')}"
        )
    if not report.get("followed_scents"):
        lines.append("result: No concrete entity scent qualified for follow-up.")
    lines += [
        "generic_pages_are_source_intelligence_only: true",
        "signal_only: true",
        "source_page_verification_required: true",
        "automatic_purchase: false",
    ]
    (output_dir / "cross-source-scent-expansion-v2.txt").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print("cross_source_scent_v2_status:", report.get("status"))
    print("cross_source_scent_v2_requests:", report.get("requests_made", 0))
    print("cross_source_scent_v2_signals:", report.get("accepted_signal_count", 0))
    print("cross_source_scent_v2_strong_scents:", report.get("strong_scent_count", 0))
    print("entity_scent_gate_clusters:", report.get("entity_cluster_count", 0))
    print("entity_scent_gate_source_intelligence:", report.get("source_intelligence_count", 0))
    return 0 if report.get("status") != "BLOCKED_CONFIGURATION" else 2


if __name__ == "__main__":
    raise SystemExit(main())
