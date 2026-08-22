from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CONTRACT_VERSION = "1.0"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    contract_version: Literal["1.0"] = CONTRACT_VERSION


class ConstraintSource(str, Enum):
    USER = "USER"
    INFERRED = "INFERRED"
    RESEARCHED = "RESEARCHED"


class Constraint(StrictContract):
    name: str = Field(min_length=1)
    value: Any
    source: ConstraintSource
    confidence: float = Field(ge=0.0, le=1.0)


class TopicInput(StrictContract):
    topic: str = Field(min_length=1)
    context: str | None = None
    goals: list[str] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("topic")
    @classmethod
    def normalize_topic(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("topic must contain non-whitespace text")
        return value


class QuestionKind(str, Enum):
    INTERNAL = "INTERNAL"
    USER = "USER"


class QuestionStatus(str, Enum):
    OPEN = "OPEN"
    ANSWERED = "ANSWERED"
    SKIPPED = "SKIPPED"
    RESEARCH_ROUTED = "RESEARCH_ROUTED"


class AnswerSource(str, Enum):
    USER = "USER"
    TOOL = "TOOL"
    SYSTEM = "SYSTEM"
    INFERENCE = "INFERENCE"


class Question(StrictContract):
    question_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    kind: QuestionKind
    purpose: str = Field(min_length=1)
    decision_variable: str | None = None
    expected_information_gain: float = Field(default=0.0, ge=0.0, le=1.0)
    interruption_cost: float = Field(default=0.0, ge=0.0, le=1.0)
    materiality: float = Field(default=0.0, ge=0.0, le=1.0)
    blocking: bool = False
    status: QuestionStatus = QuestionStatus.OPEN
    answer: Any | None = None
    answer_source: AnswerSource | None = None
    dependency_ids: list[str] = Field(default_factory=list)

    @property
    def should_ask_user(self) -> bool:
        return (
            self.kind is QuestionKind.USER
            and self.materiality >= 0.5
            and self.expected_information_gain > self.interruption_cost
            and self.status is QuestionStatus.OPEN
        )

    @model_validator(mode="after")
    def validate_question_policy(self) -> "Question":
        if self.blocking and not self.should_ask_user:
            raise ValueError(
                "blocking user questions must be open, material, and have "
                "expected_information_gain > interruption_cost"
            )
        if self.status is QuestionStatus.ANSWERED:
            if self.answer is None or self.answer_source is None:
                raise ValueError("answered questions require answer and answer_source")
        return self


class IdeaStatus(str, Enum):
    RAW = "RAW"
    CLUSTERED = "CLUSTERED"
    SEMIFINALIST = "SEMIFINALIST"
    FINALIST = "FINALIST"
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"


class Idea(StrictContract):
    idea_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    core_mechanism: str | None = None
    customer_value: str | None = None
    business_value: str | None = None
    required_capabilities: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    novelty_reason: str | None = None
    source_question_ids: list[str] = Field(default_factory=list)
    status: IdeaStatus = IdeaStatus.RAW


class ExpertMindOutput(StrictContract):
    mind_id: str = Field(min_length=1)
    lens: str = Field(min_length=1)
    assessed_idea_ids: list[str] = Field(min_length=1)
    strongest_idea_id: str = Field(min_length=1)
    independent_reasoning: list[str] = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)
    evidence_that_changes_view: list[str] = Field(default_factory=list)
    support_scores: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_idea_references(self) -> "ExpertMindOutput":
        if self.strongest_idea_id not in self.assessed_idea_ids:
            raise ValueError("strongest_idea_id must be one of assessed_idea_ids")
        unknown_scores = set(self.support_scores) - set(self.assessed_idea_ids)
        if unknown_scores:
            raise ValueError(f"support_scores contains unassessed ideas: {sorted(unknown_scores)}")
        for score in self.support_scores.values():
            if not 0.0 <= score <= 1.0:
                raise ValueError("support_scores values must be between 0 and 1")
        return self


class CritiqueDisposition(str, Enum):
    SURVIVES = "SURVIVES"
    REWORK = "REWORK"
    REJECT = "REJECT"
    NEEDS_EVIDENCE = "NEEDS_EVIDENCE"


class Critique(StrictContract):
    critique_id: str = Field(min_length=1)
    idea_id: str = Field(min_length=1)
    failure_modes: list[str] = Field(min_length=1)
    hidden_assumptions: list[str] = Field(default_factory=list)
    falsification_test: str = Field(min_length=1)
    low_cost_test: str = Field(min_length=1)
    severity: float = Field(ge=0.0, le=1.0)
    disposition: CritiqueDisposition
    rationale: list[str] = Field(default_factory=list)


class EvidenceClassification(str, Enum):
    VERIFIED_FACT = "VERIFIED_FACT"
    STRONG_EVIDENCE = "STRONG_EVIDENCE"
    WEAK_EVIDENCE = "WEAK_EVIDENCE"
    ESTIMATE = "ESTIMATE"
    ASSUMPTION = "ASSUMPTION"
    UNKNOWN = "UNKNOWN"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"


class EvidenceStance(str, Enum):
    SUPPORTS = "SUPPORTS"
    REFUTES = "REFUTES"
    NEUTRAL = "NEUTRAL"
    MIXED = "MIXED"


class Evidence(StrictContract):
    evidence_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    claim_text: str = Field(min_length=1)
    idea_id: str | None = None
    classification: EvidenceClassification
    stance: EvidenceStance = EvidenceStance.NEUTRAL
    source: str | None = None
    source_type: str | None = None
    source_ref: str | None = None
    publication_date: datetime | None = None
    retrieval_date: datetime = Field(default_factory=utc_now)
    geography: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    contradiction_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_provenance(self) -> "Evidence":
        needs_source = self.classification in {
            EvidenceClassification.VERIFIED_FACT,
            EvidenceClassification.STRONG_EVIDENCE,
            EvidenceClassification.WEAK_EVIDENCE,
            EvidenceClassification.CONFLICTING_EVIDENCE,
        }
        if needs_source and (not self.source or not self.source_type):
            raise ValueError(
                f"{self.classification.value} requires source and source_type"
            )
        if self.classification is EvidenceClassification.UNKNOWN and self.confidence > 0.5:
            raise ValueError("UNKNOWN evidence cannot carry confidence above 0.5")
        return self


class DecisionVerdict(str, Enum):
    TEST_NOW = "TEST_NOW"
    TEST_AFTER_EVIDENCE = "TEST_AFTER_EVIDENCE"
    HOLD = "HOLD"
    REWORK = "REWORK"
    REJECT = "REJECT"


class Decision(StrictContract):
    decision_id: str = Field(min_length=1)
    finalist_idea_ids: list[str] = Field(default_factory=list)
    selected_idea_ids: list[str] = Field(default_factory=list, max_length=3)
    rejected_idea_ids: list[str] = Field(default_factory=list)
    verdict: DecisionVerdict
    score_by_idea: dict[str, float] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    unresolved_unknowns: list[str] = Field(default_factory=list)
    rationale: list[str] = Field(min_length=1)
    needs_user_input: bool = False
    needs_research: bool = False
    next_question_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_decision_references(self) -> "Decision":
        selected = set(self.selected_idea_ids)
        rejected = set(self.rejected_idea_ids)
        if selected & rejected:
            raise ValueError("an idea cannot be both selected and rejected")
        if self.finalist_idea_ids and not selected.issubset(set(self.finalist_idea_ids)):
            raise ValueError("selected ideas must be finalists")
        if self.verdict in {
            DecisionVerdict.TEST_NOW,
            DecisionVerdict.TEST_AFTER_EVIDENCE,
            DecisionVerdict.REWORK,
        } and not self.selected_idea_ids:
            raise ValueError(f"{self.verdict.value} requires at least one selected idea")
        unknown_scores = set(self.score_by_idea) - set(self.finalist_idea_ids)
        if self.finalist_idea_ids and unknown_scores:
            raise ValueError(
                f"score_by_idea contains non-finalists: {sorted(unknown_scores)}"
            )
        return self


class MetricDirection(str, Enum):
    AT_LEAST = "AT_LEAST"
    AT_MOST = "AT_MOST"
    EQUALS = "EQUALS"


class MetricSpec(StrictContract):
    name: str = Field(min_length=1)
    direction: MetricDirection
    threshold: float
    unit: str = Field(min_length=1)


class Experiment(StrictContract):
    experiment_id: str = Field(min_length=1)
    idea_id: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    steps: list[str] = Field(min_length=1)
    cost_ceiling: float = Field(ge=0.0)
    time_ceiling_hours: float = Field(gt=0.0)
    success_metrics: list[MetricSpec] = Field(min_length=1)
    failure_metrics: list[MetricSpec] = Field(default_factory=list)
    stop_conditions: list[str] = Field(min_length=1)
    data_to_record: list[str] = Field(min_length=1)
    next_decision_if_passed: str = Field(min_length=1)
    next_decision_if_failed: str = Field(min_length=1)


class MemoryType(str, Enum):
    USER_CONSTRAINT = "USER_CONSTRAINT"
    IDEA_EVALUATION = "IDEA_EVALUATION"
    EXPERIMENT_OUTCOME = "EXPERIMENT_OUTCOME"
    CALIBRATION_UPDATE = "CALIBRATION_UPDATE"
    FAILURE_PATTERN = "FAILURE_PATTERN"
    SOURCE_RELIABILITY = "SOURCE_RELIABILITY"
    DOMAIN_HEURISTIC = "DOMAIN_HEURISTIC"


class MemoryTruthStatus(str, Enum):
    OBSERVED = "OBSERVED"
    VERIFIED = "VERIFIED"
    INFERRED = "INFERRED"


class MemoryRecord(StrictContract):
    memory_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    memory_type: MemoryType
    statement: str = Field(min_length=1)
    truth_status: MemoryTruthStatus
    confidence: float = Field(ge=0.0, le=1.0)
    source_decision_id: str | None = None
    source_experiment_id: str | None = None
    source_evidence_ids: list[str] = Field(default_factory=list)
    predicted_outcome: str | None = None
    actual_outcome: str | None = None
    lesson: str | None = None
    calibration_update: dict[str, float] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def prevent_unearned_verified_memory(self) -> "MemoryRecord":
        has_grounding = bool(
            self.source_evidence_ids
            or self.source_experiment_id
            or self.actual_outcome
            or self.memory_type is MemoryType.USER_CONSTRAINT
        )
        if self.truth_status is MemoryTruthStatus.VERIFIED and not has_grounding:
            raise ValueError(
                "VERIFIED memory requires evidence, experiment outcome, actual outcome, "
                "or an explicit user constraint"
            )
        return self


class RunContract(StrictContract):
    """Cross-object envelope used by adapters and acceptance tests.

    It validates referential integrity but does not dictate orchestration order.
    """

    run_id: str = Field(min_length=1)
    topic: TopicInput
    questions: list[Question] = Field(default_factory=list)
    ideas: list[Idea] = Field(default_factory=list)
    expert_outputs: list[ExpertMindOutput] = Field(default_factory=list)
    critiques: list[Critique] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    decision: Decision | None = None
    experiments: list[Experiment] = Field(default_factory=list)
    memory_records: list[MemoryRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "RunContract":
        question_ids = {q.question_id for q in self.questions}
        idea_ids = {i.idea_id for i in self.ideas}
        evidence_ids = {e.evidence_id for e in self.evidence}

        if len(question_ids) != len(self.questions):
            raise ValueError("question_id values must be unique")
        if len(idea_ids) != len(self.ideas):
            raise ValueError("idea_id values must be unique")

        for idea in self.ideas:
            missing = set(idea.source_question_ids) - question_ids
            if missing:
                raise ValueError(
                    f"idea {idea.idea_id} references unknown questions: {sorted(missing)}"
                )
        for output in self.expert_outputs:
            missing = set(output.assessed_idea_ids) - idea_ids
            if missing:
                raise ValueError(
                    f"expert {output.mind_id} references unknown ideas: {sorted(missing)}"
                )
        for critique in self.critiques:
            if critique.idea_id not in idea_ids:
                raise ValueError(
                    f"critique {critique.critique_id} references unknown idea {critique.idea_id}"
                )
        for item in self.evidence:
            if item.idea_id is not None and item.idea_id not in idea_ids:
                raise ValueError(
                    f"evidence {item.evidence_id} references unknown idea {item.idea_id}"
                )

        if self.decision is not None:
            decision_idea_ids = (
                set(self.decision.finalist_idea_ids)
                | set(self.decision.selected_idea_ids)
                | set(self.decision.rejected_idea_ids)
            )
            missing = decision_idea_ids - idea_ids
            if missing:
                raise ValueError(f"decision references unknown ideas: {sorted(missing)}")
            missing_evidence = set(self.decision.evidence_ids) - evidence_ids
            if missing_evidence:
                raise ValueError(
                    f"decision references unknown evidence: {sorted(missing_evidence)}"
                )

        selected = set(self.decision.selected_idea_ids) if self.decision else set()
        for experiment in self.experiments:
            if experiment.idea_id not in idea_ids:
                raise ValueError(
                    f"experiment {experiment.experiment_id} references unknown idea {experiment.idea_id}"
                )
            if selected and experiment.idea_id not in selected:
                raise ValueError(
                    f"experiment {experiment.experiment_id} must test a selected idea"
                )

        mind_ids = [output.mind_id for output in self.expert_outputs]
        if len(mind_ids) != len(set(mind_ids)):
            raise ValueError("mind_id values must be unique")

        return self
