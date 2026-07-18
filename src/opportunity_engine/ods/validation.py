"""Deterministic validation planning and lifecycle gate for ODS."""

from __future__ import annotations

from dataclasses import dataclass

from .bdna import BusinessBlueprint
from .models import LifecycleState, ODSSession, OpportunityCandidate, Stage, StageResult, Status


@dataclass(frozen=True)
class ValidationExperiment:
    """One practical experiment for testing a business assumption."""

    hypothesis: str
    method: str
    target_sample: str
    duration_days: int
    success_criteria: str
    failure_criteria: str
    required_metrics: tuple[str, ...]


@dataclass(frozen=True)
class ValidationExperimentResult:
    """Observed result from one completed validation experiment."""

    hypothesis: str
    completed: bool
    passed: bool
    measured_metrics: tuple[str, ...]
    evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.hypothesis.strip():
            raise ValueError("hypothesis must not be empty")
        if self.completed and not self.measured_metrics:
            raise ValueError("completed validation result requires measured_metrics")
        if self.passed and not self.completed:
            raise ValueError("an incomplete validation result cannot pass")
        if self.passed and not self.evidence:
            raise ValueError("a passing validation result requires evidence")


@dataclass(frozen=True)
class ValidationReport:
    """Decision-oriented validation plan for one business blueprint."""

    opportunity_id: str
    highest_risk_assumption: str
    experiments: tuple[ValidationExperiment, ...]
    readiness_score: float
    recommended_decision: str

    def __post_init__(self) -> None:
        if not self.opportunity_id.strip():
            raise ValueError("opportunity_id must not be empty")
        if not self.highest_risk_assumption.strip():
            raise ValueError("highest_risk_assumption must not be empty")
        if not self.experiments:
            raise ValueError("experiments must not be empty")
        if not 0 <= self.readiness_score <= 100:
            raise ValueError("readiness_score must be between 0 and 100")


def validate_opportunity(
    candidate: OpportunityCandidate,
    plan: ValidationReport,
    results: tuple[ValidationExperimentResult, ...],
) -> OpportunityCandidate:
    """Advance a hypothesis only when every planned experiment passed with evidence."""

    if candidate.lifecycle_state is not LifecycleState.HYPOTHESIS:
        raise ValueError("validation gate requires lifecycle state HYPOTHESIS")
    if plan.opportunity_id != candidate.opportunity_id:
        raise ValueError("validation plan does not belong to this opportunity")
    if len(results) != len(plan.experiments):
        raise ValueError("every planned validation experiment requires one result")

    planned = {experiment.hypothesis: experiment for experiment in plan.experiments}
    observed = {result.hypothesis: result for result in results}
    if len(observed) != len(results):
        raise ValueError("validation results contain duplicate hypotheses")
    if set(observed) != set(planned):
        raise ValueError("validation results must match the planned hypotheses")

    for hypothesis, experiment in planned.items():
        result = observed[hypothesis]
        if not result.completed:
            raise ValueError(f"validation experiment is incomplete: {hypothesis}")
        if not result.passed:
            raise ValueError(f"validation experiment failed: {hypothesis}")
        missing_metrics = set(experiment.required_metrics) - set(result.measured_metrics)
        if missing_metrics:
            missing = ", ".join(sorted(missing_metrics))
            raise ValueError(f"validation experiment is missing required metrics: {missing}")
        if not result.evidence:
            raise ValueError(f"validation experiment has no evidence: {hypothesis}")

    return candidate.transition_to(LifecycleState.VALIDATED_OPPORTUNITY)


class ValidationPlugin:
    """Converts a completed Business Blueprint into a testable validation plan."""

    name = "validation_engine"
    stage = Stage.VALIDATION

    def run(self, session: ODSSession) -> StageResult:
        bdna_result = session.results.get(Stage.BDNA)
        if bdna_result is None:
            return self._failure("validation requires a completed BDNA result")
        if bdna_result.status is not Status.COMPLETED:
            return self._failure("validation requires BDNA status completed")
        if not isinstance(bdna_result.payload, BusinessBlueprint):
            return self._failure("validation requires a BusinessBlueprint payload")

        blueprint = bdna_result.payload
        experiments = tuple(
            self._build_experiment(hypothesis, index)
            for index, hypothesis in enumerate(blueprint.hypotheses)
        )
        report = ValidationReport(
            opportunity_id=blueprint.opportunity.opportunity_id,
            highest_risk_assumption=blueprint.hypotheses[0],
            experiments=experiments,
            readiness_score=self._readiness_score(experiments),
            recommended_decision="TEST",
        )
        return StageResult(
            stage=self.stage,
            status=Status.COMPLETED,
            payload=report,
            evidence=[
                f"validation_source:{blueprint.opportunity.opportunity_id}",
                f"validation_experiments:{len(experiments)}",
                "validation_method:deterministic-alpha",
            ],
        )

    def _build_experiment(self, hypothesis: str, index: int) -> ValidationExperiment:
        if index == 0:
            return ValidationExperiment(
                hypothesis=hypothesis,
                method="Structured customer interviews and written pilot commitments",
                target_sample="20 target businesses",
                duration_days=7,
                success_criteria="At least 5 confirm the problem and 3 agree to a pilot",
                failure_criteria="Fewer than 2 confirm the problem or none accepts a pilot",
                required_metrics=(
                    "interviews_completed",
                    "problem_confirmations",
                    "pilot_commitments",
                    "stated_willingness_to_pay",
                ),
            )
        if index == 1:
            return ValidationExperiment(
                hypothesis=hypothesis,
                method="Manual concierge pilot using spreadsheets and direct coordination",
                target_sample="3 participating businesses and 20 eligible items",
                duration_days=14,
                success_criteria="At least 30% of eligible items achieve the intended outcome",
                failure_criteria="Less than 10% achieve the outcome or operations exceed recovered value",
                required_metrics=(
                    "eligible_items",
                    "successful_outcomes",
                    "recovered_value",
                    "operating_hours",
                ),
            )
        return ValidationExperiment(
            hypothesis=hypothesis,
            method="Price test with three offer levels and signed letters of intent",
            target_sample="10 qualified prospects",
            duration_days=7,
            success_criteria="At least 3 select a paid offer or sign a conditional letter of intent",
            failure_criteria="No prospect selects a paid offer",
            required_metrics=(
                "offers_presented",
                "paid_offer_selections",
                "letters_of_intent",
                "preferred_price_level",
            ),
        )

    @staticmethod
    def _readiness_score(experiments: tuple[ValidationExperiment, ...]) -> float:
        complete = sum(
            bool(item.target_sample)
            and item.duration_days > 0
            and bool(item.success_criteria)
            and bool(item.failure_criteria)
            and bool(item.required_metrics)
            for item in experiments
        )
        return round(60 + (40 * complete / len(experiments)), 2)

    def _failure(self, message: str) -> StageResult:
        return StageResult(
            stage=self.stage,
            status=Status.FAILED,
            errors=[message],
        )
