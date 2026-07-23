#!/usr/bin/env python3
"""Run a diagnostic-only audit of selected candidates through External Evidence Loop."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.external_execution_audit import (
    CandidateExecutionAudit,
    ExternalExecutionAuditReport,
    TracingSearchProvider,
    diagnose_candidate,
)
from opportunity_engine.investment_file_sync import InvestmentFileSynchronizer
from opportunity_engine.living_investment_file import LivingInvestmentFileRepository
from opportunity_engine.research_candidate import PreliminaryResearchCandidateScorer

from run_research_bootstrap import build_loop


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Brave and External Evidence execution")
    parser.add_argument("dataset", nargs="?", default="data/todays_opportunities.json")
    parser.add_argument("--output", default="data/validation/v2.7.2.4.3-external-execution-audit.json")
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
    records: list[CandidateExecutionAudit] = []
    provider = None

    for candidate in candidate_report.records:
        if not candidate.selected_for_external_research:
            continue
        loop = build_loop()
        tracing = TracingSearchProvider(loop.search_provider)
        loop.search_provider = tracing
        provider = tracing.provider
        investment_file = repository.load(candidate.opportunity_id)
        result = loop.run(investment_file)
        repository.save(investment_file)
        traces = tuple(tracing.traces)
        records.append(CandidateExecutionAudit(
            opportunity_id=candidate.opportunity_id,
            research_rank=candidate.research_rank,
            selected_for_external_research=True,
            brave_called=bool(traces),
            search_trace_count=len(traces),
            searches_executed=int(getattr(result, "searches_executed", 0)),
            searches_skipped=int(getattr(result, "searches_skipped", 0)),
            needs_detected=int(getattr(result, "needs_detected", 0)),
            response_results_total=sum(item.response_count for item in traces),
            explicit_price_results_total=sum(item.explicit_price_result_count for item in traces),
            evidence_created=int(getattr(result, "evidence_created", 0)),
            evidence_updated=int(getattr(result, "evidence_updated", 0)),
            comparables_found=int(getattr(result, "comparables_found", 0)),
            buyers_found=int(getattr(result, "buyers_found", 0)),
            scenarios_regenerated=bool(getattr(result, "scenarios_regenerated", False)),
            external_loop_errors=tuple(str(item) for item in getattr(result, "errors", ())),
            external_loop_events=tuple(str(item) for item in getattr(result, "events", ())),
            diagnosis=diagnose_candidate(result=result, traces=traces),
            search_traces=traces,
        ))

    report = ExternalExecutionAuditReport(
        selected_candidates=candidate_report.selected_count,
        audited_candidates=len(records),
        brave_request_count=sum(
            max((trace.request_count_after - trace.request_count_before), 0)
            for record in records for trace in record.search_traces
        ),
        brave_cache_hits=sum(
            max((trace.cache_hits_after - trace.cache_hits_before), 0)
            for record in records for trace in record.search_traces
        ),
        searches_executed=sum(record.searches_executed for record in records),
        results_returned=sum(record.response_results_total for record in records),
        explicit_price_results=sum(record.explicit_price_results_total for record in records),
        evidence_created=sum(record.evidence_created for record in records),
        records=tuple(records),
    )
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
