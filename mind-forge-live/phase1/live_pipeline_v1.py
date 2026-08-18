from __future__ import annotations

from hashlib import sha256

from pydantic import BaseModel, ConfigDict, model_validator

from .contracts_v1 import Question, RunContract, TopicInput
from .creative_engine_v1 import CreativeEngineResult
from .critique_engine_v1 import CritiqueEngineResult, critique_survivors
from .decision_engine_v1 import DecisionEngineResult, decide
from .experiment_engine_v1 import ExperimentEngineResult, design_experiments
from .live_model_adapter_v1 import (
    LiveBudgetGate,
    LiveModelPolicy,
    LiveUsage,
    evaluate_with_live_expert_minds,
    generate_live_ideas,
)
from .logic_engine_v1 import LogicEngineResult, evaluate_logic
from .memory_engine_v1 import MemoryEngineResult, build_planning_memory
from .question_generator_v1 import QuestionStage, build_adaptive_question_set
from .research_evidence_v1 import (
    EvidenceEngineResult,
    ResearchRouterResult,
    build_evidence,
    route_research,
)


class LiveModelForgeResult(BaseModel):
    """Seed-to-memory run with live creative/expert model calls and structural gates."""

    model_config = ConfigDict(extra="forbid")

    run_contract: RunContract
    creative: CreativeEngineResult
    logic: LogicEngineResult
    critique: CritiqueEngineResult
    research: ResearchRouterResult
    evidence_engine: EvidenceEngineResult
    decision_engine: DecisionEngineResult
    experiment_engine: ExperimentEngineResult
    memory_engine: MemoryEngineResult
    usage: LiveUsage
    user_questions_asked: list[Question] = []
    live_model_enabled: bool = True
    live_research_enabled: bool = False

    @model_validator(mode="after")
    def validate_live_boundary(self) -> "LiveModelForgeResult":
        if self.user_questions_asked:
            raise ValueError("live ideation must still start without a user questionnaire")
        if not self.live_model_enabled:
            raise ValueError("LiveModelForgeResult requires live model execution")
        if self.live_research_enabled:
            raise ValueError("this boundary does not yet enable live research")
        if self.run_contract.ideas != self.creative.ideas:
            raise ValueError("RunContract must preserve the live creative ideas")
        if self.run_contract.decision != self.decision_engine.decision:
            raise ValueError("RunContract decision must equal Decision Engine output")
        if self.run_contract.experiments != self.experiment_engine.experiments:
            raise ValueError("RunContract experiments must equal Experiment Engine output")
        if self.run_contract.memory_records != self.memory_engine.records:
            raise ValueError("RunContract memory must equal Memory Engine output")
        return self


def _live_run_id(topic: TopicInput) -> str:
    digest = sha256(topic.topic.strip().casefold().encode("utf-8")).hexdigest()[:16]
    return f"live-model-{digest}"


def run_live_model_forge(
    seed: str | TopicInput,
    *,
    policy: LiveModelPolicy | None = None,
    max_selected: int = 3,
) -> LiveModelForgeResult:
    """Run MIND FORGE with live model-backed creativity and expert lenses.

    Research remains routed but unresolved in this boundary; no live search is executed
    here. Downstream Logic, Critique, Evidence, Decision, Experiment, and Memory engines
    remain the exact structural Phase 1 guardrail implementations.
    """

    active_policy = policy or LiveModelPolicy(enabled=False)
    topic = seed if isinstance(seed, TopicInput) else TopicInput(topic=seed)
    run_id = _live_run_id(topic)
    gate = LiveBudgetGate(active_policy)

    questions, ask_now = build_adaptive_question_set(
        topic,
        stage=QuestionStage.IDEATION,
    )
    creative = generate_live_ideas(topic, questions, active_policy, gate)
    experts = evaluate_with_live_expert_minds(creative, active_policy, gate)
    logic = evaluate_logic(topic, creative, experts)
    critique = critique_survivors(creative, logic)
    research = route_research(creative, logic, critique)
    evidence_engine = build_evidence(research, ())
    decision_engine = decide(
        creative,
        logic,
        critique,
        research,
        evidence_engine,
        max_selected=max_selected,
    )
    experiment_engine = design_experiments(
        creative,
        critique,
        decision_engine,
    )
    memory_engine = build_planning_memory(
        run_id,
        decision_engine,
        experiment_engine,
    )

    contract = RunContract(
        run_id=run_id,
        topic=topic,
        questions=questions,
        ideas=creative.ideas,
        expert_outputs=experts,
        critiques=critique.critiques,
        evidence=evidence_engine.evidence,
        decision=decision_engine.decision,
        experiments=experiment_engine.experiments,
        memory_records=memory_engine.records,
    )

    return LiveModelForgeResult(
        run_contract=contract,
        creative=creative,
        logic=logic,
        critique=critique,
        research=research,
        evidence_engine=evidence_engine,
        decision_engine=decision_engine,
        experiment_engine=experiment_engine,
        memory_engine=memory_engine,
        usage=gate.usage,
        user_questions_asked=ask_now,
        live_model_enabled=True,
        live_research_enabled=False,
    )
