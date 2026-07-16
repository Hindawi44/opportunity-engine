from opportunity_engine.ods import (
    Stage,
    Status,
    ValidationPlugin,
    ValidationReport,
    run_ods,
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
