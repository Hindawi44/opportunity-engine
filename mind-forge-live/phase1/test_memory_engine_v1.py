from __future__ import annotations

import pytest

from mind_forge.contracts_v1 import MemoryTruthStatus, MemoryType, RunContract, TopicInput
from mind_forge.creative_engine_v1 import generate_ideas
from mind_forge.critique_engine_v1 import critique_survivors
from mind_forge.decision_engine_v1 import decide
from mind_forge.experiment_engine_v1 import design_experiments
from mind_forge.expert_minds_v1 import evaluate_with_expert_minds
from mind_forge.logic_engine_v1 import evaluate_logic
from mind_forge.memory_engine_v1 import ExperimentOutcome, apply_experiment_outcomes, build_planning_memory
from mind_forge.question_generator_v1 import generate_questions
from mind_forge.research_evidence_v1 import build_evidence, route_research


def _pipeline():
    topic = TopicInput(topic="تصليح الملابس")
    questions = generate_questions(topic)
    creative = generate_ideas(topic, questions)
    experts = evaluate_with_expert_minds(creative)
    logic = evaluate_logic(topic, creative, experts)
    critique = critique_survivors(creative, logic)
    router = route_research(creative, logic, critique)
    evidence = build_evidence(router)
    decision = decide(creative, logic, critique, router, evidence)
    experiments = design_experiments(creative, critique, decision)
    planning = build_planning_memory("phase1-memory-benchmark", decision, experiments)
    return topic, questions, creative, experts, critique, evidence, decision, experiments, planning


def test_planning_memory_is_inferred_not_observed_or_verified() -> None:
    _, _, _, _, _, _, decision, _, planning = _pipeline()

    assert len(planning.records) == len(decision.decision.selected_idea_ids) == 3
    assert all(item.truth_status is MemoryTruthStatus.INFERRED for item in planning.records)
    assert all(item.memory_type is MemoryType.IDEA_EVALUATION for item in planning.records)
    assert planning.observed_experiment_ids == []
    assert planning.contains_unearned_verified_memory is False


def test_real_outcome_creates_observed_experiment_memory() -> None:
    _, _, _, _, _, _, _, experiments, planning = _pipeline()
    experiment = experiments.experiments[0]
    outcome = ExperimentOutcome(
        experiment_id=experiment.experiment_id,
        passed=True,
        actual_outcome="The bounded pilot met both success metrics without triggering the stop condition.",
        observations=["Cycle time improved on the measured sample."],
        metric_values={"example_metric": 1.0},
        lesson="Retain the mechanism for the next decision cycle, but do not generalize beyond the observed sample.",
    )

    result = apply_experiment_outcomes(planning, experiments, [outcome])
    observed = [item for item in result.records if item.truth_status is MemoryTruthStatus.OBSERVED]
    assert len(observed) == 1
    assert observed[0].memory_type is MemoryType.EXPERIMENT_OUTCOME
    assert observed[0].source_experiment_id == experiment.experiment_id
    assert observed[0].actual_outcome == outcome.actual_outcome
    assert experiment.experiment_id in result.observed_experiment_ids
    assert not any(item.truth_status is MemoryTruthStatus.VERIFIED for item in result.records)


def test_failed_outcome_adds_grounded_failure_pattern() -> None:
    _, _, _, _, _, _, _, experiments, planning = _pipeline()
    experiment = experiments.experiments[0]
    outcome = ExperimentOutcome(
        experiment_id=experiment.experiment_id,
        passed=False,
        actual_outcome="The workflow change moved the queue downstream and failed the end-to-end test.",
        observations=["Downstream queue increased by three jobs."],
        lesson="Do not repeat this bottleneck change without redesigning the downstream constraint.",
    )

    result = apply_experiment_outcomes(planning, experiments, [outcome])
    failure_records = [item for item in result.records if item.memory_type is MemoryType.FAILURE_PATTERN]
    assert len(failure_records) == 1
    assert failure_records[0].truth_status is MemoryTruthStatus.OBSERVED
    assert failure_records[0].source_experiment_id == experiment.experiment_id
    assert failure_records[0].actual_outcome == outcome.actual_outcome


def test_memory_engine_rejects_unknown_or_duplicate_outcomes() -> None:
    _, _, _, _, _, _, _, experiments, planning = _pipeline()
    unknown = ExperimentOutcome(
        experiment_id="experiment-does-not-exist",
        passed=True,
        actual_outcome="No valid experiment exists for this outcome.",
        lesson="Invalid fixture.",
    )
    with pytest.raises(ValueError):
        apply_experiment_outcomes(planning, experiments, [unknown])

    experiment = experiments.experiments[0]
    duplicate = ExperimentOutcome(
        experiment_id=experiment.experiment_id,
        passed=True,
        actual_outcome="Observed outcome.",
        lesson="Observed lesson.",
    )
    with pytest.raises(ValueError):
        apply_experiment_outcomes(planning, experiments, [duplicate, duplicate])


def test_memory_records_fit_the_full_canonical_run_contract() -> None:
    topic, questions, creative, experts, critique, evidence, decision, experiments, planning = _pipeline()
    experiment = experiments.experiments[0]
    outcome = ExperimentOutcome(
        experiment_id=experiment.experiment_id,
        passed=False,
        actual_outcome="Observed bounded failure during the pilot.",
        observations=["Stop condition triggered."],
        lesson="Rework before retesting.",
    )
    memory = apply_experiment_outcomes(planning, experiments, [outcome])

    contract = RunContract(
        run_id=planning.run_id,
        topic=topic,
        questions=questions,
        ideas=creative.ideas,
        expert_outputs=experts,
        critiques=critique.critiques,
        evidence=evidence.evidence,
        decision=decision.decision,
        experiments=experiments.experiments,
        memory_records=memory.records,
    )
    assert contract.memory_records
    assert not any(item.truth_status is MemoryTruthStatus.VERIFIED for item in contract.memory_records)
