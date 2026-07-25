from pathlib import Path


REPORT = Path("docs/WORKFLOW_WAVE4A_V266_HISTORICAL_DIAGNOSTIC_AUDIT_REPORT_v1.0.md")
WORKFLOW = Path(".github/workflows/v2.6.6-live-dry-run.yml")


def test_wave4a_report_records_exact_historical_contract():
    text = REPORT.read_text(encoding="utf-8")

    required = (
        "6cb22262a18950c045ba8deb4ae70dbc2cc6811e",
        "a7af4f99e3c6e5b299c2248e8ea2fa3713e057e7",
        "workflow_dispatch",
        "opportunity_limit",
        "BRAVE_API_KEY",
        "scripts/run_production_readiness.py",
        "scripts/run_daily_pipeline.py",
        "tests/test_production_readiness.py",
        "v2.6.6-live-dry-run",
        "retention: 14 days",
        "MANUAL_VERIFICATION_REQUIRED",
        "FINAL_MANUAL_RUN_THEN_DISABLE_IN_SEPARATE_PR",
    )
    for value in required:
        assert value in text


def test_wave4a_report_preserves_workflow_and_no_automatic_action_contract():
    report = REPORT.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "schedule:" not in workflow
    assert "pull_request:" not in workflow
    assert "workflow_dispatch:" in workflow
    assert "contents: read" in workflow
    assert "retention-days: 14" in workflow
    assert "name: v2.6.6-live-dry-run" in workflow

    assert "Wave 4A changes no workflow" in report
    assert "must not be removed" in report
    assert "do not expose secret values" in report
    assert "purchase, bid, contact" not in workflow.lower()
