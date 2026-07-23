#!/usr/bin/env python3
"""Run V2.7.2.4.4 Brave transport and response audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from opportunity_engine.brave_transport_audit import (
    AuditedBraveSearchProvider,
    BraveTransportRecord,
    summarize_transport,
)
from opportunity_engine.investment_file_sync import InvestmentFileSynchronizer
from opportunity_engine.living_investment_file import LivingInvestmentFileRepository
from opportunity_engine.research_candidate import PreliminaryResearchCandidateScorer

from run_research_bootstrap import build_loop


def _candidate_record(
    *,
    candidate: Any,
    result: Any,
    requests: list[BraveTransportRecord],
) -> dict[str, Any]:
    last = requests[-1] if requests else None
    return {
        "opportunity_id": candidate.opportunity_id,
        "research_rank": candidate.research_rank,
        "selected_for_external_research": True,
        "request_sent": any(item.request_sent for item in requests),
        "http_status": last.http_status if last else None,
        "response_time_ms": last.response_time_ms if last else None,
        "results_count": sum(item.results_count for item in requests),
        "body_preview": last.body_preview if last else "",
        "stage_reached": last.stage_reached if last else "prepare_request",
        "transport_error": next((item.transport_error for item in requests if item.transport_error), None),
        "parse_error": next((item.parse_error for item in requests if item.parse_error), None),
        "evidence_created": int(getattr(result, "evidence_created", 0)),
        "evidence_updated": int(getattr(result, "evidence_updated", 0)),
        "comparables_found": int(getattr(result, "comparables_found", 0)),
        "buyers_found": int(getattr(result, "buyers_found", 0)),
        "external_loop_errors": [str(item) for item in getattr(result, "errors", ())],
        "requests": [item.to_dict() for item in requests],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Brave HTTP transport and response parsing")
    parser.add_argument("dataset", nargs="?", default="data/todays_opportunities.json")
    parser.add_argument("--output", default="data/validation/v2.7.2.4.4-brave-transport-response-audit.json")
    parser.add_argument("--investment-files-dir", default="data/investment_files")
    parser.add_argument("--threshold", type=float, default=25.0)
    parser.add_argument("--selection-limit", type=int, default=3)
    args = parser.parse_args()

    payload = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    InvestmentFileSynchronizer(args.investment_files_dir).sync_payload(payload)
    candidate_report = PreliminaryResearchCandidateScorer(
        threshold=args.threshold,
        selection_limit=args.selection_limit,
    ).evaluate_payload(payload)

    repository = LivingInvestmentFileRepository(args.investment_files_dir)
    loop = build_loop()
    audited_provider = AuditedBraveSearchProvider(loop.search_provider)
    loop.search_provider = audited_provider

    candidate_records: list[dict[str, Any]] = []
    for candidate in candidate_report.records:
        if not candidate.selected_for_external_research:
            continue
        start = len(audited_provider.records)
        investment_file = repository.load(candidate.opportunity_id)
        result = loop.run(investment_file)
        repository.save(investment_file)
        requests = audited_provider.records[start:]
        audited_provider.mark_forwarded(requests)
        candidate_records.append(_candidate_record(candidate=candidate, result=result, requests=requests))

    report = {
        "schema_version": "2.7.2.4.4",
        "audit_scope": "Brave transport and response only",
        "selected_candidates": candidate_report.selected_count,
        "audited_candidates": len(candidate_records),
        "summary": summarize_transport(audited_provider.records),
        "records": candidate_records,
    }
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
