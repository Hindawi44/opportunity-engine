from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts_v1 import Critique, CritiqueDisposition
from .creative_engine_v1 import CreativeEngineResult
from .logic_engine_v1 import LogicEngineResult


class CritiqueEngineResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    critiqued_idea_ids: list[str] = Field(min_length=1)
    critiques: list[Critique] = Field(min_length=1)
    survived_idea_ids: list[str] = Field(default_factory=list)
    rework_idea_ids: list[str] = Field(default_factory=list)
    needs_evidence_idea_ids: list[str] = Field(default_factory=list)
    rejected_idea_ids: list[str] = Field(default_factory=list)
    devils_advocate_applied: bool = True

    @model_validator(mode="after")
    def validate_critique_partition(self) -> "CritiqueEngineResult":
        critiqued = set(self.critiqued_idea_ids)
        if len(critiqued) != len(self.critiqued_idea_ids):
            raise ValueError("critiqued idea IDs must be unique")
        critique_ids = {critique.idea_id for critique in self.critiques}
        if critique_ids != critiqued or len(critique_ids) != len(self.critiques):
            raise ValueError("critiques must cover each critiqued idea exactly once")

        groups = [
            set(self.survived_idea_ids),
            set(self.rework_idea_ids),
            set(self.needs_evidence_idea_ids),
            set(self.rejected_idea_ids),
        ]
        if any(groups[i] & groups[j] for i in range(len(groups)) for j in range(i + 1, len(groups))):
            raise ValueError("critique partitions must be disjoint")
        if set().union(*groups) != critiqued:
            raise ValueError("critique partitions must exhaust the critiqued universe")
        if not self.devils_advocate_applied:
            raise ValueError("Critique Engine V1 requires Devil's Advocate pressure")
        return self


_TEST_SPECS: dict[str, tuple[str, str, str, float]] = {
    "bottleneck_redesign": (
        "The apparent bottleneck may only move the queue downstream, leaving end-to-end throughput unchanged.",
        "The mechanism is falsified if removing the targeted constraint fails to improve end-to-end cycle time or simply creates a larger downstream queue.",
        "Measure a small sample of jobs before and after one reversible workflow change; compare total cycle time, queue location, and rework.",
        0.00,
    ),
    "standardization": (
        "The work mix may contain too many profitable exceptions for a small standardized menu to remain useful.",
        "The mechanism is falsified if a material share of real jobs cannot fit the packages without exceptions, re-quoting, or quality loss.",
        "Classify a recent sample of jobs against a draft three-to-five-package menu and record fit rate, exception rate, and margin variance.",
        0.02,
    ),
    "premium_speed": (
        "A priority lane may cannibalize scarce capacity and reduce reliability or contribution from the standard queue.",
        "The mechanism is falsified if priority jobs reduce contribution per capacity-hour or materially worsen on-time performance for standard work.",
        "Run a tightly capped priority pilot on a few jobs and record premium paid, skilled minutes consumed, displacement, and both queues' on-time delivery.",
        0.15,
    ),
    "automation_intake": (
        "Pre-qualification may misclassify edge cases and push hidden complexity into later rework.",
        "The mechanism is falsified if automated/pre-structured intake produces an unacceptable mismatch rate versus skilled human assessment.",
        "Replay the draft intake on a small set of real or historical cases and compare its routing/quote inputs with a skilled human review.",
        0.05,
    ),
    "data_feedback": (
        "Data collection may become overhead if the selected fields do not change any concrete operating decision.",
        "The mechanism is falsified if the minimal dataset fails to change or clarify a pricing, capacity, routing, or offer decision after a bounded collection period.",
        "Capture only a few decision-linked fields for a short period and require a written decision log showing what changed because of each signal.",
        0.00,
    ),
    "adjacent_bundle": (
        "The adjacent need may be too weak or operationally distracting to justify a bundle around the core service.",
        "The mechanism is falsified if customers show low attach intent or the added coordination cost overwhelms the incremental value.",
        "Offer one narrowly defined adjacent bundle to a small customer sample and record attach rate, willingness-to-pay, extra handling time, and confusion points.",
        0.12,
    ),
}

_FALLBACK_SPEC = (
    "The mechanism may depend on an unresolved assumption whose failure makes the value path uneconomic or operationally fragile.",
    "The mechanism is falsified if its key assumption fails under a small reversible test tied to the promised customer and business value.",
    "Run the smallest reversible test that exposes the key assumption while measuring one customer-value and one business-value signal.",
    0.05,
)


def _severity(dependency_risk: float, evidence_debt: float, reversibility: float, risk_count: int, penalty: float) -> float:
    value = (
        0.15
        + 0.25 * dependency_risk
        + 0.25 * evidence_debt
        + 0.15 * (1.0 - reversibility)
        + 0.10 * min(risk_count / 2.0, 1.0)
        + penalty
    )
    return round(max(0.0, min(1.0, value)), 4)


def _disposition(severity: float) -> CritiqueDisposition:
    if severity >= 0.75:
        return CritiqueDisposition.REJECT
    if severity >= 0.58:
        return CritiqueDisposition.REWORK
    if severity >= 0.50:
        return CritiqueDisposition.NEEDS_EVIDENCE
    return CritiqueDisposition.SURVIVES


def critique_survivors(
    creative: CreativeEngineResult,
    logic: LogicEngineResult,
) -> CritiqueEngineResult:
    """Attack only Logic survivors before research/decision.

    The critique stage converts each surviving mechanism into explicit failure modes
    and falsification/low-cost tests. It does not turn assumptions into facts and it
    does not resurrect ideas held or rejected by Logic.
    """

    ideas_by_id = {idea.idea_id: idea for idea in creative.ideas}
    logic_by_id = {item.idea_id: item for item in logic.assessments}
    survivor_ids = list(logic.survivor_idea_ids)
    if not survivor_ids:
        raise ValueError("Critique Engine requires at least one Logic survivor")
    missing = set(survivor_ids) - set(ideas_by_id)
    if missing:
        raise ValueError(f"Logic survivors are missing from the creative universe: {sorted(missing)}")

    critiques: list[Critique] = []
    survived: list[str] = []
    rework: list[str] = []
    needs_evidence: list[str] = []
    rejected: list[str] = []

    for idea_id in survivor_ids:
        idea = ideas_by_id[idea_id]
        logic_item = logic_by_id[idea_id]
        failure, falsification, low_cost, penalty = _TEST_SPECS.get(
            logic_item.mechanism_family, _FALLBACK_SPEC
        )
        severity = _severity(
            logic_item.dependency_risk,
            logic_item.evidence_debt,
            logic_item.reversibility_score,
            len(idea.risks),
            penalty,
        )
        disposition = _disposition(severity)

        failure_modes = [failure]
        for risk in idea.risks:
            if risk not in failure_modes:
                failure_modes.append(risk)

        critique = Critique(
            critique_id=f"critique-{idea_id}",
            idea_id=idea_id,
            failure_modes=failure_modes,
            hidden_assumptions=list(idea.assumptions),
            falsification_test=falsification,
            low_cost_test=low_cost,
            severity=severity,
            disposition=disposition,
            rationale=[
                f"Devil's Advocate severity is derived from structural dependency risk ({logic_item.dependency_risk:.2f}), evidence debt ({logic_item.evidence_debt:.2f}), reversibility ({logic_item.reversibility_score:.2f}), and mechanism-specific fragility.",
                "Disposition is a pre-evidence stress result, not a claim that the failure mode has occurred in the real market.",
            ],
        )
        critiques.append(critique)

        if disposition is CritiqueDisposition.SURVIVES:
            survived.append(idea_id)
        elif disposition is CritiqueDisposition.REWORK:
            rework.append(idea_id)
        elif disposition is CritiqueDisposition.NEEDS_EVIDENCE:
            needs_evidence.append(idea_id)
        else:
            rejected.append(idea_id)

    return CritiqueEngineResult(
        critiqued_idea_ids=survivor_ids,
        critiques=critiques,
        survived_idea_ids=survived,
        rework_idea_ids=rework,
        needs_evidence_idea_ids=needs_evidence,
        rejected_idea_ids=rejected,
        devils_advocate_applied=True,
    )
