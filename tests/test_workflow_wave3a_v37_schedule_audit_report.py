from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "WORKFLOW_WAVE3A_V37_SCHEDULE_AUDIT_REPORT_v1.0.md"
V37 = ROOT / ".github" / "workflows" / "v3.7-production-pilot.yml"
V32 = ROOT / ".github" / "workflows" / "v3.2-continuous-opportunity-monitoring.yml"


def test_wave3a_report_records_current_v37_contract() -> None:
    report = REPORT.read_text(encoding="utf-8")
    workflow = V37.read_text(encoding="utf-8")

    assert "2 — Review One Opportunity End to End" in report
    assert "17 * * * *" in report
    assert "workflow_dispatch" in report
    assert "v3.7-production-pilot-summary" in report
    assert "artifacts/v3.7-production-pilot-summary.json" in report
    assert "MANUAL_VERIFICATION_REQUIRED" in report
    assert "3e6c65449e093e7051f980ef4b1b04af3470a443" in report

    assert "pull_request:" in workflow
    assert "workflow_dispatch:" in workflow
    assert 'cron: "17 * * * *"' in workflow
    assert "pytest tests/test_v37_production_pilot.py -q" in workflow
    assert "run: pytest -q" in workflow


def test_wave3a_report_records_exact_minute_17_collision() -> None:
    report = REPORT.read_text(encoding="utf-8")
    v37 = V37.read_text(encoding="utf-8")
    v32 = V32.read_text(encoding="utf-8")

    assert 'cron: "17 * * * *"' in v37
    assert "cron: '17 * * * *'" in v32
    assert "confirmed trigger collision" in report.lower()


def test_wave3a_is_documentation_only() -> None:
    report = REPORT.read_text(encoding="utf-8")

    assert "Workflow behavior changed:** none" in report
    assert "This proposal is not yet implemented" in report
    assert "No workflow changed in this audit" in report
