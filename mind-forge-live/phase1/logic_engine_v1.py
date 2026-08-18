from __future__ import annotations

from enum import Enum
from statistics import mean
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts_v1 import Constraint, ExpertMindOutput, Idea, TopicInput
from .creative_engine_v1 import CreativeEngineResult


class LogicDisposition(str, Enum):
    SURVIVE = "SURVIVE"
    HOLD_FOR_EVIDENCE = "HOLD_FOR_EVIDENCE"
    REJECT_CONSTRAINT = "REJECT_CONSTRAINT"
    REJECT_STRUCTURAL = "REJECT_STRUCTURAL"


class LogicAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idea_id: str = Field(min_length=1)
    mechanism_family: str = Field(min_length=1)
    feasibility_score: float = Field(ge=0.0, le=1.0)
    reversibility_score: float = Field(ge=0.0, le=1.0)
    dependency_risk: float = Field(ge=0.0, le=1.0)
    evidence_debt: float = Field(ge=0.0, le=1.0)
    simplicity_score: float = Field(ge=0.0, le=1.0)
    logic_score: float = Field(ge=0.0, le=1.0)
    expert_support_mean: float | None = Field(default=None, ge=0.0, le=1.0)
    constraint_violations: list[str] = Field(default_factory=list)
    structural_failures: list[str] = Field(default_factory=list)
    unresolved_assumptions: list[str] = Field(default_factory=list)
    rationale: list[str] = Field(min_length=1)
    disposition: LogicDisposition


class LogicEngineResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessed_idea_ids: list[str] = Field(min_length=1)
    survivor_idea_ids: list[str] = Field(default_factory=list)
    held_idea_ids: list[str] = Field(default_factory=list)
    rejected_idea_ids: list[str] = Field(default_factory=list)
    assessments: list[LogicAssessment] = Field(min_length=1)
    survivor_threshold: float = Field(ge=0.0, le=1.0)
    uses_expert_popularity_for_gating: bool = False

    @model_validator(mode="after")
    def validate_partition(self) -> "LogicEngineResult":
        assessed = set(self.assessed_idea_ids)
        if len(assessed) != len(self.assessed_idea_ids):
            raise ValueError("assessed idea IDs must be unique")
        assessment_ids = {item.idea_id for item in self.assessments}
        if assessment_ids != assessed or len(assessment_ids) != len(self.assessments):
            raise ValueError("assessments must cover the assessed universe exactly once")

        survivors = set(self.survivor_idea_ids)
        held = set(self.held_idea_ids)
        rejected = set(self.rejected_idea_ids)
        if survivors & held or survivors & rejected or held & rejected:
            raise ValueError("logic partitions must be disjoint")
        if survivors | held | rejected != assessed:
            raise ValueError("logic partitions must exhaust the assessed universe")
        if self.uses_expert_popularity_for_gating:
            raise ValueError("expert popularity may not gate Logic Engine survival")
        return self


# Structural priors only. They express testability/dependency burden of a mechanism,
# not market truth. Any future evidence-backed logic layer may replace these priors.
_FAMILY_PRIORS: dict[str, tuple[float, float, float, float]] = {
    "bottleneck_redesign": (0.88, 0.92, 0.25, 0.35),
    "standardization": (0.86, 0.88, 0.28, 0.32),
    "premium_speed": (0.78, 0.85, 0.40, 0.45),
    "recurring_membership": (0.58, 0.75, 0.55, 0.72),
    "outcome_guarantee": (0.62, 0.70, 0.58, 0.70),
    "distribution_partnership": (0.68, 0.80, 0.55, 0.60),
    "b2b_embedding": (0.66, 0.68, 0.62, 0.62),
    "automation_intake": (0.76, 0.84, 0.42, 0.50),
    "mobile_access": (0.64, 0.82, 0.58, 0.66),
    "demand_aggregation": (0.67, 0.80, 0.54, 0.58),
    "circular_recovery": (0.60, 0.85, 0.62, 0.68),
    "replication_licensing": (0.48, 0.55, 0.78, 0.82),
    "data_feedback": (0.84, 0.95, 0.25, 0.35),
    "adjacent_bundle": (0.72, 0.86, 0.45, 0.52),
}

_DEFAULT_PRIOR = (0.55, 0.70, 0.60, 0.70)
_SURVIVOR_THRESHOLD = 0.65


def _normalized_constraint_map(constraints: Iterable[Constraint]) -> dict[str, list[Constraint]]:
    result: dict[str, list[Constraint]] = {}
    for constraint in constraints:
        result.setdefault(constraint.name.strip().casefold(), []).append(constraint)
    return result


def _as_string_set(value: object) -> set[str]:
    if isinstance(value, str):
        return {value.strip().casefold()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return {str(item).strip().casefold() for item in value}
    return set()


def _constraint_violations(
    topic: TopicInput,
    idea: Idea,
    family: str,
) -> list[str]:
    constraints = _normalized_constraint_map(topic.constraints)
    violations: list[str] = []

    forbidden_caps: set[str] = set()
    for item in constraints.get("forbidden_capabilities", []):
        forbidden_caps |= _as_string_set(item.value)
    used_caps = {cap.strip().casefold() for cap in idea.required_capabilities}
    blocked = sorted(used_caps & forbidden_caps)
    if blocked:
        violations.append(f"forbidden capabilities required: {', '.join(blocked)}")

    forbidden_families: set[str] = set()
    for item in constraints.get("forbidden_mechanism_families", []):
        forbidden_families |= _as_string_set(item.value)
    if family.casefold() in forbidden_families:
        violations.append(f"mechanism family forbidden by explicit constraint: {family}")

    for item in constraints.get("max_required_capabilities", []):
        try:
            maximum = int(item.value)
        except (TypeError, ValueError):
            continue
        if len(idea.required_capabilities) > maximum:
            violations.append(
                f"requires {len(idea.required_capabilities)} capabilities above allowed maximum {maximum}"
            )

    for item in constraints.get("max_assumptions", []):
        try:
            maximum = int(item.value)
        except (TypeError, ValueError):
            continue
        if len(idea.assumptions) > maximum:
            violations.append(
                f"carries {len(idea.assumptions)} assumptions above allowed maximum {maximum}"
            )

    return violations


def _structural_failures(idea: Idea) -> list[str]:
    failures: list[str] = []
    if not idea.core_mechanism or not idea.core_mechanism.strip():
        failures.append("missing core mechanism")
    if not idea.business_value or not idea.business_value.strip():
        failures.append("missing business-value logic")
    if not idea.customer_value or not idea.customer_value.strip():
        failures.append("missing customer-value logic")
    return failures


def _expert_support_mean(idea_id: str, expert_outputs: Iterable[ExpertMindOutput]) -> float | None:
    values = [
        output.support_scores[idea_id]
        for output in expert_outputs
        if idea_id in output.support_scores
    ]
    return round(mean(values), 4) if values else None


def _logic_score(
    feasibility: float,
    reversibility: float,
    dependency_risk: float,
    evidence_debt: float,
    simplicity: float,
) -> float:
    score = (
        0.35 * feasibility
        + 0.20 * reversibility
        + 0.20 * (1.0 - dependency_risk)
        + 0.15 * (1.0 - evidence_debt)
        + 0.10 * simplicity
    )
    return round(max(0.0, min(1.0, score)), 4)


def evaluate_logic(
    topic: TopicInput,
    creative: CreativeEngineResult,
    expert_outputs: Iterable[ExpertMindOutput] = (),
) -> LogicEngineResult:
    """Apply structural logic before critique/research, without inventing facts.

    Expert support is recorded for later synthesis but is intentionally excluded from
    the survival formula and from hard constraint/structural gates.
    """

    ideas = list(creative.ideas)
    idea_ids = [idea.idea_id for idea in ideas]
    family_map = creative.mechanism_family_by_idea_id
    if set(family_map) != set(idea_ids):
        raise ValueError("creative family map must exactly cover the logic candidate universe")

    experts = list(expert_outputs)
    for output in experts:
        unknown = set(output.assessed_idea_ids) - set(idea_ids)
        if unknown:
            raise ValueError(f"expert {output.mind_id} references ideas outside the logic universe")

    assessments: list[LogicAssessment] = []
    survivors: list[str] = []
    held: list[str] = []
    rejected: list[str] = []

    for idea in ideas:
        family = family_map[idea.idea_id]
        feasibility, reversibility, dependency_risk, evidence_debt = _FAMILY_PRIORS.get(
            family, _DEFAULT_PRIOR
        )
        simplicity = max(0.0, 1.0 - min(len(idea.required_capabilities), 6) / 6.0)
        score = _logic_score(
            feasibility,
            reversibility,
            dependency_risk,
            evidence_debt,
            simplicity,
        )
        violations = _constraint_violations(topic, idea, family)
        failures = _structural_failures(idea)

        if violations:
            disposition = LogicDisposition.REJECT_CONSTRAINT
            rejected.append(idea.idea_id)
            rationale = [
                "Rejected because an explicit TopicInput constraint is violated; expert popularity cannot override this gate.",
                *violations,
            ]
        elif failures:
            disposition = LogicDisposition.REJECT_STRUCTURAL
            rejected.append(idea.idea_id)
            rationale = [
                "Rejected because the idea is structurally incomplete enough that logic cannot evaluate a coherent mechanism/value path.",
                *failures,
            ]
        elif score >= _SURVIVOR_THRESHOLD:
            disposition = LogicDisposition.SURVIVE
            survivors.append(idea.idea_id)
            rationale = [
                "Survives the structural logic gate on testability, reversibility, dependency burden, and evidence debt.",
                "This is not a market validation claim; unresolved assumptions remain assumptions until evidence or experiment resolves them.",
            ]
        else:
            disposition = LogicDisposition.HOLD_FOR_EVIDENCE
            held.append(idea.idea_id)
            rationale = [
                "Held rather than rejected because the concept is logically coherent but carries too much dependency/evidence burden for the first survivor set.",
                "A later Evidence or Experiment stage may upgrade or downgrade it.",
            ]

        assessments.append(
            LogicAssessment(
                idea_id=idea.idea_id,
                mechanism_family=family,
                feasibility_score=feasibility,
                reversibility_score=reversibility,
                dependency_risk=dependency_risk,
                evidence_debt=evidence_debt,
                simplicity_score=round(simplicity, 4),
                logic_score=score,
                expert_support_mean=_expert_support_mean(idea.idea_id, experts),
                constraint_violations=violations,
                structural_failures=failures,
                unresolved_assumptions=list(idea.assumptions),
                rationale=rationale,
                disposition=disposition,
            )
        )

    return LogicEngineResult(
        assessed_idea_ids=idea_ids,
        survivor_idea_ids=survivors,
        held_idea_ids=held,
        rejected_idea_ids=rejected,
        assessments=assessments,
        survivor_threshold=_SURVIVOR_THRESHOLD,
        uses_expert_popularity_for_gating=False,
    )
