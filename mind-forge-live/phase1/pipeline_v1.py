from __future__ import annotations

from hashlib import sha256
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts_v1 import Question, RunContract, TopicInput
from .creative_engine_v1 import CreativeEngineResult, generate_ideas
from .critique_engine_v1 import CritiqueEngineResult, critique_survivors
from .decision_engine_v1 import DecisionEngineResult, decide
from .experiment_engine_v1 import ExperimentEngineResult, design_experiments
from .expert_minds_v1 import evaluate_with_expert_minds
from .logic_engine_v1 import LogicEngineResult, evaluate_logic
from .memory_engine_v1 import MemoryEngineResult, build_planning_memory
from .question_generator_v1 import QuestionStage, build_adaptive_question_set
from .research_evidence_v1 import (
    EvidenceEngineResult,
    EvidenceObservation,
    ResearchRoute,
    ResearchRouterResult,
    build_evidence,
    route_research,
)


class Phase1ForgeResult(BaseModel):
    """One-call structural Phase 1 result from raw seed through planning memory."""

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
    user_questions_asked: list[Question] = Field(default_factory=list)
    offline_structural_only: bool = True

    @model_validator(mode="after")
    def validate_pipeline_alignment(self) -> "Phase1ForgeResult":
        contract = self.run_contract
        idea_ids = {item.idea_id for item in contract.ideas}

        if self.user_questions_asked:
            raise ValueError("Phase 1 ideation must start without interrupting the user")
        if not self.offline_structural_only:
            raise ValueError("Phase 1 orchestrator is explicitly structural/offline in this validation layer")
        if set(self.creative.mechanism_family_by_idea_id) != idea_ids:
            raise ValueError("creative result must align exactly with RunContract ideas")
        if set(self.logic.assessed_idea_ids) != idea_ids:
            raise ValueError("Logic must assess the full creative universe")
        if set(self.critique.critiqued_idea_ids) != set(self.logic.survivor_idea_ids):
            raise ValueError("Critique must operate exactly on Logic survivors")
        if set(self.research.candidate_idea_ids) != set(self.critique.critiqued_idea_ids):
            raise ValueError("Research Router must operate exactly on critiqued candidates")
        if contract.decision != self.decision_engine.decision:
            raise ValueError("RunContract decision must equal Decision Engine output")
        if contract.experiments != self.experiment_engine.experiments:
            raise ValueError("RunContract experiments must equal Experiment Engine output")
        if contract.memory_records != self.memory_engine.records:
            raise ValueError("RunContract memory must equal Memory Engine output")
        return self


def _run_id(topic: TopicInput) -> str:
    digest = sha256(topic.topic.strip().casefold().encode("utf-8")).hexdigest()[:16]
    return f"phase1-{digest}"


def _ground_external_research(
    topic: TopicInput,
    router: ResearchRouterResult,
) -> ResearchRouterResult:
    """Make the first paid searches validate the seed's real target market.

    Phase 1 ideas are deliberately mechanism-diverse, but their first assumptions can
    be too generic for live search. The first two external requests therefore answer
    the two market questions that must precede mechanism-specific optimization:
    current target-market demand and current direct alternatives/competition.

    Request IDs and idea ownership remain unchanged so the existing contracts,
    Decision Engine, budgets, and evidence lineage stay backward compatible.
    """

    external_ids = set(router.external_request_ids)
    external_rank = 0
    grounded_requests = []

    for request in router.requests:
        if request.request_id not in external_ids:
            grounded_requests.append(request)
            continue

        if external_rank == 0:
            grounded_requests.append(
                request.model_copy(
                    update={
                        "claim_text": (
                            f"The target market for {topic.topic} has enough current local demand "
                            "and customer activity to justify a low-cost paid pilot before larger capital is committed."
                        ),
                        "why_material": (
                            f"A real-world demand floor for {topic.topic} is decision-critical; "
                            "without it, optimizing packaging, speed, or operations is premature."
                        ),
                        "route": ResearchRoute.PUBLIC_DATA,
                        "acceptable_source_types": [
                            "official statistics",
                            "primary public dataset",
                            "public data source",
                        ],
                    }
                )
            )
        elif external_rank == 1:
            grounded_requests.append(
                request.model_copy(
                    update={
                        "claim_text": (
                            f"Direct competitors and substitutes serving customers for {topic.topic} "
                            "leave a meaningful local gap in product, price, convenience, availability, or experience."
                        ),
                        "why_material": (
                            f"The opportunity in {topic.topic} depends on what customers can already buy locally; "
                            "a competitor gap can change whether to test, rework, or reject the concept."
                        ),
                        "route": ResearchRoute.WEB,
                        "acceptable_source_types": [
                            "direct competitor/public offer",
                            "local business listing",
                            "web/public source",
                        ],
                    }
                )
            )
        else:
            grounded_requests.append(request)

        external_rank += 1

    return router.model_copy(update={"requests": grounded_requests})


def run_phase1_forge(
    seed: str | TopicInput,
    *,
    evidence_observations: Iterable[EvidenceObservation] = (),
    max_selected: int = 3,
) -> Phase1ForgeResult:
    """Run the complete zero-paid-call Phase 1 structural pipeline from one seed.

    The function intentionally does not execute web research, model calls, or real
    experiments. It creates the internal question space, diverse ideas, independent
    expert reviews, Logic/Critique gates, material research routes, canonical evidence
    state, a bounded decision, executable experiment designs when allowed, and safe
    planning memory. External adapters can later supply EvidenceObservation objects
    without changing these contracts or guardrails.
    """

    topic = seed if isinstance(seed, TopicInput) else TopicInput(topic=seed)
    run_id = _run_id(topic)

    questions, ask_now = build_adaptive_question_set(
        topic,
        stage=QuestionStage.IDEATION,
    )
    creative = generate_ideas(topic, questions)
    experts = evaluate_with_expert_minds(creative)
    logic = evaluate_logic(topic, creative, experts)
    critique = critique_survivors(creative, logic)
    research = _ground_external_research(
        topic,
        route_research(creative, logic, critique),
    )
    evidence_engine = build_evidence(research, evidence_observations)
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

    return Phase1ForgeResult(
        run_contract=contract,
        creative=creative,
        logic=logic,
        critique=critique,
        research=research,
        evidence_engine=evidence_engine,
        decision_engine=decision_engine,
        experiment_engine=experiment_engine,
        memory_engine=memory_engine,
        user_questions_asked=ask_now,
        offline_structural_only=True,
    )
