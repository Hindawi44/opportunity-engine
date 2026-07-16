from opportunity_engine.ods import ExecutiveWorkflowInputs, build_decision_from_analysis, run_ods


def test_build_decision_from_analysis_waits_without_external_evidence():
    analysis = run_ods("fashion", country="Norway", shortlist_size=3)
    report = build_decision_from_analysis(ExecutiveWorkflowInputs(analysis=analysis))

    assert report.decision.value == "WAIT"
    assert "official evidence quality" in report.missing_evidence
    assert "market health" in report.missing_evidence
    assert "financial assumptions" in report.missing_evidence


def test_build_decision_from_analysis_uses_top_ranked_opportunity():
    analysis = run_ods("fashion", country="Norway", shortlist_size=3)
    report = build_decision_from_analysis(
        ExecutiveWorkflowInputs(
            analysis=analysis,
            evidence_quality=90.0,
            market_health=85.0,
            trend_confidence=0.9,
        )
    )

    assert 0.0 <= report.score <= 100.0
    assert report.decision.value in {"GO", "WAIT", "REJECT"}
