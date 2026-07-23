#!/usr/bin/env python3
"""Run V2.7.2.4.7 Comparable Acceptance Audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from opportunity_engine.comparable_acceptance_audit import (
    ComparableAcceptanceAuditedProvider,
    summarize_acceptance,
)
from opportunity_engine.investment_file_sync import InvestmentFileSynchronizer
from opportunity_engine.living_investment_file import LivingInvestmentFileRepository
from opportunity_engine.research_candidate import PreliminaryResearchCandidateScorer

from run_research_bootstrap import build_loop, comparable_adapter


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit comparable acceptance of Brave results")
    parser.add_argument("dataset", nargs="?", default="data/todays_opportunities.json")
    parser.add_argument(
        "--output",
        default="data/validation/v2.7.2.4.7-comparable-acceptance-audit.json",
    )
    parser.add_argument("--investment-files-dir", default="data/investment_files")
    parser.add_argument("--threshold", type=float, default=25.0)
    parser.add_argument("--selection-limit", type=int, default=3)
    parser.add_argument("--row-limit", type=int, default=20)
    args = parser.parse_args()

    payload = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    InvestmentFileSynchronizer(args.investment_files_dir).sync_payload(payload)
    candidate_report = PreliminaryResearchCandidateScorer(
        threshold=args.threshold,
        selection_limit=args.selection_limit,
    ).evaluate_payload(payload)

    repository = LivingInvestmentFileRepository(args.investment_files_dir)
    loop = build_loop()
    audited_provider = ComparableAcceptanceAuditedProvider(
        loop.search_provider,
        comparable_adapter=comparable_adapter,
        comparables_engine=loop.market_comparables_engine,
        row_limit=args.row_limit,
    )
    loop.search_provider = audited_provider

    candidate_records: list[dict[str, Any]] = []
    for candidate in candidate_report.records:
        if not candidate.selected_for_external_research:
            continue
        start = len(audited_provider.audits)
        investment_file = repository.load(candidate.opportunity_id)
        result = loop.run(investment_file)
        repository.save(investment_file)
        audits = audited_provider.audits[start:]
        candidate_records.append(
            {
                "opportunity_id": candidate.opportunity_id,
                "research_rank": candidate.research_rank,
                "needs_detected": int(getattr(result, "needs_detected", 0)),
                "searches_executed": int(getattr(result, "searches_executed", 0)),
                "evidence_created": int(getattr(result, "evidence_created", 0)),
                "comparables_found": int(getattr(result, "comparables_found", 0)),
                "buyers_found": int(getattr(result, "buyers_found", 0)),
                "errors": [str(item) for item in getattr(result, "errors", ())],
                "searches": [item.to_dict() for item in audits],
            }
        )

    report = {
        "schema_version": "2.7.2.4.7",
        "audit_scope": "Comparable adapter and engine acceptance only",
        "selected_candidates": candidate_report.selected_count,
        "audited_candidates": len(candidate_records),
        "summary": summarize_acceptance(audited_provider.audits),
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
