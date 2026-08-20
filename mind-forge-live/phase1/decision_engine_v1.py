from __future__ import annotations

from statistics import mean

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts_v1 import (
    CritiqueDisposition,
    Decision,
    DecisionVerdict,
    EvidenceClassification,
)
from .creative_engine_v1 import CreativeEngineResult
from .critique_engine_v1 import CritiqueEngineResult
from .logic_engine_v1 import LogicDisposition, LogicEngineResult
from .research_evidence_v1 import EvidenceEngineResult, ResearchRoute, ResearchRouterResult


class DecisionCandidateScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idea_id: str = Field(min_length=1)
    logic_score: float = Field(ge=0.0, le=1.0)
    critique_robustness: float = Field(ge=0.0, le=1.0)
    evidence_quality: float = Field(ge=0.0, le=1.0)
    expert_support: float = Field(ge=0.0, le=1.0)
    composite_score: float = Field(ge=0.0, le=1.0)
    eligible: bool
    eligibility_reason: str = Field(min_length=1)


class DecisionEngineResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Decision
    candidate_scores: list[DecisionCandidateScore] = Field(min_length=1)
    eligible_idea_ids: list[str] = Field(default_factory=list)
    max_selected: int = Field(default=3, ge=1, le=3)
    expert_popularity_can_override_logic: bool = False
    unresolved_external_research_blocks_test_now: bool = True

    @model_validator(mode="after")
    def validate_guards(self) -> "DecisionEngineResult":
        if self.expert_popularity_can_override_logic:
            raise ValueError("expert popularity may not override Logic/Critique eligibility")
        if not self.unresolved_external_research_blocks_test_now:
            raise ValueError("unresolved material external research must block TEST_NOW")
        selected = set(self.decision.selected_idea_ids)
        if not selected.issubset(set(self.eligible_idea_ids)):
            raise ValueError("selected ideas must be Decision Engine eligible")
        if len(selected) > self.max_selected:
            raise ValueError("selected idea count exceeds max_selected")
        return self


_EVIDENCE_WEIGHT: dict[EvidenceClassification, float] = {
    EvidenceClassification.VERIFIED_FACT: 1.00,
    EvidenceClassification.STRONG_EVIDENCE: 0.90,
    EvidenceClassification.WEAK_EVIDENCE: 0.62,
    EvidenceClassification.ESTIMATE: 0.48,
    EvidenceClassification.ASSUMPTION: 0.30,
    EvidenceClassification.UNKNOWN: 0.15,
    EvidenceClassification.CONFLICTING_EVIDENCE: 0.25,
}


def _evidence_quality(idea_id: str, evidence: EvidenceEngineResult) -> float:
    values = [
        _EVIDENCE_WEIGHT[item.classification]
        for item in evidence.evidence
        if item.idea_id == idea_id
    ]
    return round(mean(values), 4) if values else 0.0


def _composite(logic_score: float, severity: float, evidence_quality: float, expert_support: float) -> float:
    # Eligibility is decided before this score. Expert popularity is intentionally a
    # small ranking term and therefore cannot rescue an ineligible idea.
    value = (
        0.50 * logic_score
        + 0.25 * (1.0 - severity)
        + 0.15 * evidence_quality
        + 0.10 * expert_support
    )
    return round(max(0.0, min(1.0, value)), 4)


def _has_unresolved_external_request(
    idea_id: str,
    router: ResearchRouterResult,
    evidence: EvidenceEngineResult,
) -> bool:
    unresolved = set(evidence.unresolved_request_ids)
    return any(
        request.idea_id == idea_id
        and request.request_id in unresolved
        and request.route in {ResearchRoute.WEB, ResearchRoute.PUBLIC_DATA, ResearchRoute.CALCULATOR}
        for request in router.requests
    )


def decide(
    creative: CreativeEngineResult,
    logic: LogicEngineResult,
    critique: CritiqueEngineResult,
    router: ResearchRouterResult,
    evidence: EvidenceEngineResult,
    *,
    max_selected: int = 3,
) -> DecisionEngineResult:
    """Create a bounded canonical Decision after Logic, Critique, and Evidence.

    Hard gates are applied before ranking. Only ideas that survived Logic and Devil's
    Advocate can be TEST_NOW finalists. REWORK/NEEDS_EVIDENCE remain visible but do
    not outrank a true survivor merely because experts like them.
    """

    if max_selected < 1 or max_selected > 3:
        raise ValueError("max_selected must be between 1 and 3")

    idea_ids = {idea.idea_id for idea in creative.ideas}
    logic_by_id = {item.idea_id: item for item in logic.assessments}
    critique_by_id = {item.idea_id: item for item in critique.critiques}

    if not set(critique_by_id).issubset(idea_ids):
        raise ValueError("Critique contains ideas outside the creative universe")

    candidate_scores: list[DecisionCandidateScore] = []
    eligible: list[str] = []
    rework_pool: list[str] = []
    evidence_pool: list[str] = []

    for idea_id in critique.critiqued_idea_ids:
        logic_item = logic_by_id[idea_id]
        critique_item = critique_by_id[idea_id]
        expert_support = logic_item.expert_support_mean or 0.0
        evidence_quality = _evidence_quality(idea_id, evidence)
        composite = _composite(
            logic_item.logic_score,
            critique_item.severity,
            evidence_quality,
            expert_support,
        )

        is_eligible = (
            logic_item.disposition is LogicDisposition.SURVIVE
            and critique_item.disposition is CritiqueDisposition.SURVIVES
        )
        if is_eligible:
            reason = "Passed Logic and Devil's Advocate hard gates."
            eligible.append(idea_id)
        elif critique_item.disposition is CritiqueDisposition.REWORK:
            reason = "Logically coherent but Devil's Advocate requires rework before selection."
            rework_pool.append(idea_id)
        elif critique_item.disposition is CritiqueDisposition.NEEDS_EVIDENCE:
            reason = "Material uncertainty requires evidence before selection."
            evidence_pool.append(idea_id)
        elif critique_item.disposition is CritiqueDisposition.REJECT:
            reason = "Rejected by Devil's Advocate hard gate."
        else:
            reason = "Not eligible for the current decision stage."

        candidate_scores.append(
            DecisionCandidateScore(
                idea_id=idea_id,
                logic_score=logic_item.logic_score,
                critique_robustness=round(1.0 - critique_item.severity, 4),
                evidence_quality=evidence_quality,
                expert_support=expert_support,
                composite_score=composite,
                eligible=is_eligible,
                eligibility_reason=reason,
            )
        )

    score_by_id = {item.idea_id: item.composite_score for item in candidate_scores}
    eligible_sorted = sorted(eligible, key=lambda idea_id: (score_by_id[idea_id], idea_id), reverse=True)
    selected = eligible_sorted[:max_selected]

    if selected:
        blocked_by_external = [
            idea_id
            for idea_id in selected
            if _has_unresolved_external_request(idea_id, router, evidence)
        ]
        verdict = (
            DecisionVerdict.TEST_AFTER_EVIDENCE
            if blocked_by_external
            else DecisionVerdict.TEST_NOW
        )
        finalists = eligible_sorted
        unresolved = []
        if blocked_by_external:
            unresolved.append(
                "Selected idea(s) still depend on unresolved material external research: "
                + ", ".join(blocked_by_external)
            )
        for idea_id in selected:
            for item in evidence.evidence:
                if item.idea_id == idea_id and item.classification in {
                    EvidenceClassification.UNKNOWN,
                    EvidenceClassification.ASSUMPTION,
                    EvidenceClassification.CONFLICTING_EVIDENCE,
                }:
                    unresolved.append(f"{idea_id}: {item.claim_text}")
        needs_research = bool(blocked_by_external)
        rationale = [
            "Selected only ideas that passed both Logic and Devil's Advocate hard gates.",
            "Composite score ranks eligible survivors using logic, critique robustness, evidence quality, and a bounded 10% expert-support term.",
            "Unresolved operational assumptions do not block TEST_NOW when the routed next step is a bounded experiment designed to resolve them.",
        ]
    elif evidence_pool:
        evidence_sorted = sorted(evidence_pool, key=lambda idea_id: (score_by_id[idea_id], idea_id), reverse=True)
        selected = evidence_sorted[:max_selected]
        finalists = evidence_sorted
        verdict = DecisionVerdict.TEST_AFTER_EVIDENCE
        unresolved = ["No idea passed Devil's Advocate; selected candidates require material evidence before testing."]
        needs_research = True
        rationale = ["No current survivor is strong enough for TEST_NOW; evidence must resolve material uncertainty first."]
    elif rework_pool:
        rework_sorted = sorted(rework_pool, key=lambda idea_id: (score_by_id[idea_id], idea_id), reverse=True)
        selected = rework_sorted[:max_selected]
        finalists = rework_sorted
        verdict = DecisionVerdict.REWORK
        unresolved = ["No idea passed Devil's Advocate; selected candidates require structural rework."]
        needs_research = False
        rationale = ["No idea cleared the critique gate; rework is required before evidence or experiment spend."]
    else:
        selected = []
        finalists = []
        verdict = DecisionVerdict.HOLD
        unresolved = ["No candidate currently clears the required Logic/Critique gates."]
        needs_research = False
        rationale = ["Decision is HOLD because no candidate is eligible for action."]

    finalist_evidence_ids = [
        item.evidence_id
        for item in evidence.evidence
        if item.idea_id in set(finalists)
    ]
    explicit_rejected = sorted(set(logic.rejected_idea_ids) | set(critique.rejected_idea_ids))
    confidence = round(min(0.85, mean(score_by_id[idea_id] for idea_id in selected)), 4) if selected else 0.35

    decision = Decision(
        decision_id="decision-phase1-v1",
        finalist_idea_ids=finalists,
        selected_idea_ids=selected,
        rejected_idea_ids=explicit_rejected,
        verdict=verdict,
        score_by_idea={idea_id: score_by_id[idea_id] for idea_id in finalists},
        confidence=confidence,
        evidence_ids=finalist_evidence_ids,
        unresolved_unknowns=unresolved,
        rationale=rationale,
        needs_user_input=False,
        needs_research=needs_research,
        next_question_ids=[],
    )

    return DecisionEngineResult(
        decision=decision,
        candidate_scores=candidate_scores,
        eligible_idea_ids=eligible_sorted,
        max_selected=max_selected,
        expert_popularity_can_override_logic=False,
        unresolved_external_research_blocks_test_now=True,
    )
