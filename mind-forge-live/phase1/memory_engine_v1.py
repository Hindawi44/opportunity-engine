from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts_v1 import MemoryRecord, MemoryTruthStatus, MemoryType
from .decision_engine_v1 import DecisionEngineResult
from .experiment_engine_v1 import ExperimentEngineResult


class ExperimentOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_id: str = Field(min_length=1)
    passed: bool
    actual_outcome: str = Field(min_length=1)
    observations: list[str] = Field(default_factory=list)
    metric_values: dict[str, float] = Field(default_factory=dict)
    lesson: str = Field(min_length=1)


class MemoryEngineResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    records: list[MemoryRecord] = Field(default_factory=list)
    observed_experiment_ids: list[str] = Field(default_factory=list)
    contains_unearned_verified_memory: bool = False

    @model_validator(mode="after")
    def validate_memory_safety(self) -> "MemoryEngineResult":
        if self.contains_unearned_verified_memory:
            raise ValueError("Memory Engine may not emit unearned VERIFIED memory")
        memory_ids = [item.memory_id for item in self.records]
        if len(memory_ids) != len(set(memory_ids)):
            raise ValueError("memory IDs must be unique")
        observed_sources = {
            item.source_experiment_id
            for item in self.records
            if item.truth_status is MemoryTruthStatus.OBSERVED and item.source_experiment_id
        }
        if not set(self.observed_experiment_ids).issubset(observed_sources):
            raise ValueError("observed_experiment_ids must be grounded by OBSERVED memory records")
        if any(item.truth_status is MemoryTruthStatus.VERIFIED for item in self.records):
            raise ValueError("Phase 1 Memory Engine does not auto-promote any record to VERIFIED")
        return self


def build_planning_memory(
    run_id: str,
    decision_result: DecisionEngineResult,
    experiment_result: ExperimentEngineResult,
) -> MemoryEngineResult:
    """Store decision/experiment plans as INFERRED memory only.

    Selection and experiment design are system conclusions, not observed outcomes.
    They remain explicitly INFERRED until a real experiment outcome is supplied.
    """

    decision = decision_result.decision
    experiments_by_idea = {item.idea_id: item for item in experiment_result.experiments}
    records: list[MemoryRecord] = []

    for idea_id in decision.selected_idea_ids:
        experiment = experiments_by_idea.get(idea_id)
        predicted = experiment.hypothesis if experiment is not None else None
        records.append(
            MemoryRecord(
                memory_id=f"memory-plan-{run_id}-{idea_id}",
                run_id=run_id,
                memory_type=MemoryType.IDEA_EVALUATION,
                statement=(
                    f"Idea {idea_id} was selected under decision {decision.decision_id} with verdict {decision.verdict.value}; "
                    "this is a planning conclusion, not a validated market fact."
                ),
                truth_status=MemoryTruthStatus.INFERRED,
                confidence=decision.confidence,
                source_decision_id=decision.decision_id,
                predicted_outcome=predicted,
                lesson="Await evidence or experiment outcome before increasing truth status.",
            )
        )

    return MemoryEngineResult(
        run_id=run_id,
        records=records,
        observed_experiment_ids=[],
        contains_unearned_verified_memory=False,
    )


def apply_experiment_outcomes(
    planning: MemoryEngineResult,
    experiment_result: ExperimentEngineResult,
    outcomes: list[ExperimentOutcome],
) -> MemoryEngineResult:
    """Append OBSERVED learning from supplied experiment outcomes.

    The function never fabricates outcomes and never marks an observation VERIFIED.
    Failed experiments additionally create a grounded FAILURE_PATTERN memory so the
    next cycle can avoid repeating the same failure blindly.
    """

    experiments = {item.experiment_id: item for item in experiment_result.experiments}
    seen_outcomes: set[str] = set()
    records = list(planning.records)
    observed_ids = list(planning.observed_experiment_ids)

    for outcome in outcomes:
        if outcome.experiment_id not in experiments:
            raise ValueError(f"outcome references unknown experiment {outcome.experiment_id}")
        if outcome.experiment_id in seen_outcomes:
            raise ValueError(f"duplicate outcome for experiment {outcome.experiment_id}")
        seen_outcomes.add(outcome.experiment_id)

        experiment = experiments[outcome.experiment_id]
        status_word = "passed" if outcome.passed else "failed"
        records.append(
            MemoryRecord(
                memory_id=f"memory-outcome-{planning.run_id}-{outcome.experiment_id}",
                run_id=planning.run_id,
                memory_type=MemoryType.EXPERIMENT_OUTCOME,
                statement=f"Experiment {outcome.experiment_id} {status_word}: {outcome.actual_outcome}",
                truth_status=MemoryTruthStatus.OBSERVED,
                confidence=0.90,
                source_experiment_id=outcome.experiment_id,
                predicted_outcome=experiment.hypothesis,
                actual_outcome=outcome.actual_outcome,
                lesson=outcome.lesson,
            )
        )
        observed_ids.append(outcome.experiment_id)

        if not outcome.passed:
            observations = "; ".join(outcome.observations) if outcome.observations else outcome.actual_outcome
            records.append(
                MemoryRecord(
                    memory_id=f"memory-failure-{planning.run_id}-{outcome.experiment_id}",
                    run_id=planning.run_id,
                    memory_type=MemoryType.FAILURE_PATTERN,
                    statement=(
                        f"Failure pattern observed for idea {experiment.idea_id}: {observations}"
                    ),
                    truth_status=MemoryTruthStatus.OBSERVED,
                    confidence=0.85,
                    source_experiment_id=outcome.experiment_id,
                    actual_outcome=outcome.actual_outcome,
                    lesson=outcome.lesson,
                )
            )

    return MemoryEngineResult(
        run_id=planning.run_id,
        records=records,
        observed_experiment_ids=observed_ids,
        contains_unearned_verified_memory=False,
    )
