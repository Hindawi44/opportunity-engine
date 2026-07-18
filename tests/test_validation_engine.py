import pytest

from opportunity_engine.ods import (
    LifecycleState,
    OpportunityCandidate,
    Stage,
    Status,
    ValidationExperiment,
    ValidationExperimentResult,
    ValidationPlugin,
    ValidationReport,
    run_ods,
    validate_opportunity,
)


def test_validation_report_contains_decision_ready_experiments() -> None:
    result = run_ods("Fashion", country="Norway")
    report = result.validation

    assert isinstance(report, ValidationReport)
    assert report.highest_risk_assumption
    assert report.recommended_decision == "TEST"
    assert report.readiness_score == 100.0
    assert len(report.experiments) == len(result.blueprint.hypotheses)
    assert all(item.duration_days > 0 for item in report.experiments)
    assert all(item.success_criteria for item in report.experiments)
    assert all(item.failure_criteria for item in report.experiments)


def test_validation_plugin_requires_bdna_result() -> None:
    from opportunity_engine.ods import ODSRequest, ODSSession

    plugin = ValidationPlugin()
    session = ODSSession(request=ODSRequest(subject="Fashion", country="Norway"))
    outcome = plugin.run(session)

    assert outcome.stage is Stage.VALIDATION
    assert outcome.status is Status.FAILED
    assert outcome.errors == ["validation requires a completed BDNA result"]


def _candidate(state: LifecycleState = LifecycleState.HYPOTHESIS) -> OpportunityCandidate:
    return OpportunityCandidate(
        opportunity_id="opp-1",
        title="Validated business hypothesis",
        description="A hypothesis that requires field validation",
        category="test",
        evidence=("source:test",),
        confidence=0.7,
        lifecycle_state=state,
    )


def _plan() -> ValidationReport:
    return ValidationReport(
        opportunity_id="opp-1",
        highest_risk_assumption="Customers will pay",
        experiments=(
            ValidationExperiment(
                hypothesis="Customers will pay",
                method="Paid pilot",
                target_sample="10 prospects",
                duration_days=7,
                success_criteria="3 paid pilots",
                failure_criteria="0 paid pilots",
                required_metrics=("prospects_contacted", "paid_pilots"),
            ),
        ),
        readiness_score=100.0,
        recommended_decision="TEST",
    )


def _passing_result() -> ValidationExperimentResult:
    return ValidationExperimentResult(
        hypothesis="Customers will pay",
        completed=True,
        passed=True,
        measured_metrics=("prospects_contacted", "paid_pilots"),
        evidence=("pilot:customer-a", "pilot:customer-b", "pilot:customer-c"),
    )


def test_completed_passing_experiment_advances_hypothesis() -> None:
    validated = validate_opportunity(_candidate(), _plan(), (_passing_result(),))
    assert validated.lifecycle_state is LifecycleState.VALIDATED_OPPORTUNITY


def test_validation_gate_rejects_failed_experiment() -> None:
    failed = ValidationExperimentResult(
        hypothesis="Customers will pay",
        completed=True,
        passed=False,
        measured_metrics=("prospects_contacted", "paid_pilots"),
        evidence=("pilot:no-sales",),
    )
    with pytest.raises(ValueError, match="validation experiment failed"):
        validate_opportunity(_candidate(), _plan(), (failed,))


def test_validation_gate_rejects_missing_required_metrics() -> None:
    incomplete_metrics = ValidationExperimentResult(
        hypothesis="Customers will pay",
        completed=True,
        passed=True,
        measured_metrics=("prospects_contacted",),
        evidence=("pilot:customer-a",),
    )
    with pytest.raises(ValueError, match="missing required metrics"):
        validate_opportunity(_candidate(), _plan(), (incomplete_metrics,))


def test_validation_gate_requires_hypothesis_state() -> None:
    with pytest.raises(ValueError, match="requires lifecycle state HYPOTHESIS"):
        validate_opportunity(
            _candidate(LifecycleState.VERIFIED_LEAD),
            _plan(),
            (_passing_result(),),
        )


def test_validation_gate_requires_matching_plan() -> None:
    wrong_plan = ValidationReport(
        opportunity_id="opp-2",
        highest_risk_assumption="Customers will pay",
        experiments=_plan().experiments,
        readiness_score=100.0,
        recommended_decision="TEST",
    )
    with pytest.raises(ValueError, match="does not belong"):
        validate_opportunity(_candidate(), wrong_plan, (_passing_result(),))
