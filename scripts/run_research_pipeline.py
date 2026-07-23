#!/usr/bin/env python3
"""Run evidence collection, scoring and scenario regeneration from a snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.evidence_store import EvidenceRepository
from opportunity_engine.investment_file_sync import InvestmentFileSynchronizer
from opportunity_engine.living_investment_file import LivingInvestmentFileRepository
from opportunity_engine.research_pipeline import ResearchPipelineOrchestrator


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the v2.5.2 research pipeline")
    parser.add_argument("snapshot", nargs="?", default="data/todays_opportunities.json")
    parser.add_argument("--investment-files-dir", default="data/investment_files")
    parser.add_argument("--evidence-dir", default="data/evidence")
    parser.add_argument("--run-log-dir", default="data/research_runs")
    args = parser.parse_args()

    payload = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    synchronizer = InvestmentFileSynchronizer(args.investment_files_dir)
    sync = synchronizer.sync_payload(payload)
    investment_repo = LivingInvestmentFileRepository(args.investment_files_dir)
    orchestrator = ResearchPipelineOrchestrator(
        evidence_repository=EvidenceRepository(args.evidence_dir),
        investment_repository=investment_repo,
        run_log_root=args.run_log_dir,
    )

    intelligence_by_id = payload.get("intelligence_by_id", {})
    discovery_by_id = payload.get("discovery_by_id", {})
    results = []
    for row in payload.get("rows", []):
        opportunity_id = str(row.get("opportunity_id") or "").strip()
        if not opportunity_id:
            continue
        item = investment_repo.load(opportunity_id)
        result = orchestrator.run(
            item,
            row,
            intelligence=intelligence_by_id.get(opportunity_id),
            discovery=discovery_by_id.get(opportunity_id),
        )
        results.append(result.__dict__)

    response = {
        "investment_files_created": sync.created_count,
        "investment_files_updated": sync.updated_count,
        "investment_files_unchanged": sync.unchanged_count,
        "research_cycles": len(results),
        "results": results,
    }
    print(json.dumps(response, ensure_ascii=False, sort_keys=True, default=list))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
