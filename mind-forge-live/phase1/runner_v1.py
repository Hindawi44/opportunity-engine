from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel, ConfigDict, model_validator

from .contracts_v1 import EvidenceClassification, RunContract
from .decision_engine_v1 import DecisionEngineResult, decide
from .experiment_engine_v1 import ExperimentEngineResult, design_experiments
from .live_research_adapter_v1 import (
    LiveResearchResult,
    ResearchExecutor,
    ResearchPolicy,
    execute_research_requests,
)
from .memory_engine_v1 import MemoryEngineResult, build_planning_memory
from .pipeline_v1 import Phase1ForgeResult, run_phase1_forge
from .research_evidence_v1 import EvidenceEngineResult, build_evidence


class MindForgeRunnerResult(BaseModel):
    """One-seed MIND FORGE result after optional Router-approved live research."""

    model_config = ConfigDict(extra="forbid")

    seed: str
    baseline: Phase1ForgeResult
    research: LiveResearchResult | None = None
    evidence_engine: EvidenceEngineResult
    decision_engine: DecisionEngineResult
    experiment_engine: ExperimentEngineResult
    memory_engine: MemoryEngineResult
    run_contract: RunContract
    live_research_requested: bool = False

    @model_validator(mode="after")
    def validate_runner_alignment(self) -> "MindForgeRunnerResult":
        if self.live_research_requested and self.research is None:
            raise ValueError("live research was requested but no research result exists")
        if not self.live_research_requested and self.research is not None:
            raise ValueError("research result exists even though live research was not requested")
        if self.run_contract.decision != self.decision_engine.decision:
            raise ValueError("Runner contract decision must equal Decision Engine output")
        if self.run_contract.experiments != self.experiment_engine.experiments:
            raise ValueError("Runner contract experiments must equal Experiment Engine output")
        if self.run_contract.memory_records != self.memory_engine.records:
            raise ValueError("Runner contract memory must equal Memory Engine output")
        if self.run_contract.evidence != self.evidence_engine.evidence:
            raise ValueError("Runner contract evidence must equal Evidence Engine output")

        if self.research is not None:
            live_refs = {item.source_ref for item in self.research.observations if item.source_ref}
            for item in self.run_contract.evidence:
                if item.source_ref in live_refs and item.classification is EvidenceClassification.VERIFIED_FACT:
                    raise ValueError("Runner may not promote live research directly to VERIFIED_FACT")
        return self


def _rebuild_run_contract(
    baseline: Phase1ForgeResult,
    evidence_engine: EvidenceEngineResult,
    decision_engine: DecisionEngineResult,
    experiment_engine: ExperimentEngineResult,
    memory_engine: MemoryEngineResult,
) -> RunContract:
    original = baseline.run_contract
    return RunContract(
        run_id=original.run_id,
        topic=original.topic,
        questions=original.questions,
        ideas=original.ideas,
        expert_outputs=original.expert_outputs,
        critiques=original.critiques,
        evidence=evidence_engine.evidence,
        decision=decision_engine.decision,
        experiments=experiment_engine.experiments,
        memory_records=memory_engine.records,
    )


def run_mind_forge(
    seed: str,
    *,
    live_research: bool = False,
    research_policy: ResearchPolicy | None = None,
    research_executor: ResearchExecutor | None = None,
    max_selected: int = 3,
) -> MindForgeRunnerResult:
    """Run MIND FORGE from one raw seed, with live research explicitly opt-in.

    Default execution is zero-paid-call structural Phase 1. When live_research=True,
    the caller must supply an explicitly enabled ResearchPolicy. Router-approved
    external requests are executed, normalized into EvidenceObservation objects,
    reclassified only by Evidence Engine, and then Decision/Experiment/Memory are
    rebuilt from the evidence-aware state.
    """

    baseline = run_phase1_forge(seed, max_selected=max_selected)

    if not live_research:
        return MindForgeRunnerResult(
            seed=baseline.run_contract.topic.topic,
            baseline=baseline,
            research=None,
            evidence_engine=baseline.evidence_engine,
            decision_engine=baseline.decision_engine,
            experiment_engine=baseline.experiment_engine,
            memory_engine=baseline.memory_engine,
            run_contract=baseline.run_contract,
            live_research_requested=False,
        )

    if research_policy is None or not research_policy.enabled:
        raise RuntimeError(
            "live research requires an explicitly enabled ResearchPolicy; default remains OFF"
        )

    research = execute_research_requests(
        baseline.research,
        policy=research_policy,
        executor=research_executor,
    )
    evidence_engine = build_evidence(
        baseline.research,
        research.observations,
    )
    decision_engine = decide(
        baseline.creative,
        baseline.logic,
        baseline.critique,
        baseline.research,
        evidence_engine,
        max_selected=max_selected,
    )
    experiment_engine = design_experiments(
        baseline.creative,
        baseline.critique,
        decision_engine,
    )
    memory_engine = build_planning_memory(
        baseline.run_contract.run_id,
        decision_engine,
        experiment_engine,
    )
    run_contract = _rebuild_run_contract(
        baseline,
        evidence_engine,
        decision_engine,
        experiment_engine,
        memory_engine,
    )

    return MindForgeRunnerResult(
        seed=baseline.run_contract.topic.topic,
        baseline=baseline,
        research=research,
        evidence_engine=evidence_engine,
        decision_engine=decision_engine,
        experiment_engine=experiment_engine,
        memory_engine=memory_engine,
        run_contract=run_contract,
        live_research_requested=True,
    )


def build_runner_summary(result: MindForgeRunnerResult) -> dict[str, object]:
    evidence_counts = Counter(item.classification.value for item in result.evidence_engine.evidence)
    research = result.research
    live_sources = []
    if research is not None:
        live_sources = [
            {
                "source": item.source,
                "source_type": item.source_type,
                "source_ref": item.source_ref,
                "stance": item.stance.value,
                "confidence": item.confidence,
            }
            for item in research.observations
        ]

    return {
        "status": "MIND_FORGE_RUN_COMPLETE",
        "seed": result.seed,
        "run_id": result.run_contract.run_id,
        "idea_count": len(result.run_contract.ideas),
        "expert_mind_count": len(result.run_contract.expert_outputs),
        "logic_survivor_count": len(result.baseline.logic.survivor_idea_ids),
        "critique_survivor_count": len(result.baseline.critique.survived_idea_ids),
        "research_request_count": len(result.baseline.research.requests),
        "router_external_request_count": len(result.baseline.research.external_request_ids),
        "live_research_requested": result.live_research_requested,
        "research_executed_request_ids": (
            research.executed_request_ids if research is not None else []
        ),
        "research_skipped_request_ids": (
            research.skipped_request_ids if research is not None else []
        ),
        "research_usage": (
            research.usage.model_dump() if research is not None else {
                "search_operations": 0,
                "results_returned": 0,
                "estimated_cost_usd": 0.0,
            }
        ),
        "evidence_classes": dict(evidence_counts),
        "conflicting_claim_ids": result.evidence_engine.conflicting_claim_ids,
        "decision_verdict": result.decision_engine.decision.verdict.value,
        "selected_idea_ids": result.decision_engine.decision.selected_idea_ids,
        "decision_confidence": result.decision_engine.decision.confidence,
        "experiment_count": len(result.experiment_engine.experiments),
        "memory_record_count": len(result.memory_engine.records),
        "live_sources": live_sources,
    }


def _write_outputs(result: MindForgeRunnerResult, output_dir: str | None) -> None:
    if not output_dir:
        return
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "mind-forge-runner-summary.json").write_text(
        json.dumps(build_runner_summary(result), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (root / "mind-forge-run-contract.json").write_text(
        result.run_contract.model_dump_json(indent=2),
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mind-forge-runner-v1",
        description="Run MIND FORGE V1 from one raw seed.",
    )
    parser.add_argument("seed", help="Raw seed, for example: محل شاي في نامسوس")
    parser.add_argument(
        "--live-research",
        action="store_true",
        help="Execute Router-approved live research. OFF unless explicitly requested.",
    )
    parser.add_argument(
        "--confirm-paid-live-research",
        choices=("NO", "YES"),
        default="NO",
        help="Explicit paid-research confirmation. Default: NO.",
    )
    parser.add_argument("--research-model", default="gpt-5.6-luna")
    parser.add_argument("--max-search-operations", type=int, default=2)
    parser.add_argument("--max-research-cost-usd", type=float, default=0.02)
    parser.add_argument("--max-selected", type=int, default=3)
    parser.add_argument("--output-dir", default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    if args.live_research:
        if args.confirm_paid_live_research != "YES":
            parser.error(
                "--live-research requires --confirm-paid-live-research YES; no paid call was made"
            )
        os.environ["MIND_FORGE_LIVE_RESEARCH_ENABLED"] = "1"
        policy = ResearchPolicy(
            enabled=True,
            model=args.research_model,
            max_search_operations=args.max_search_operations,
            max_estimated_cost_usd=args.max_research_cost_usd,
        )
        result = run_mind_forge(
            args.seed,
            live_research=True,
            research_policy=policy,
            max_selected=args.max_selected,
        )
    else:
        if args.confirm_paid_live_research == "YES":
            parser.error("paid research confirmation was supplied without --live-research")
        result = run_mind_forge(
            args.seed,
            max_selected=args.max_selected,
        )

    _write_outputs(result, args.output_dir)
    print(json.dumps(build_runner_summary(result), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
