from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "WORKFLOW_WAVE3C_V32_MONITORING_OWNERSHIP_AUDIT_REPORT_v1.0.md"
V32 = ROOT / ".github" / "workflows" / "v3.2-continuous-opportunity-monitoring.yml"
V37 = ROOT / ".github" / "workflows" / "v3.7-production-pilot.yml"
V33 = ROOT / ".github" / "workflows" / "v3.3-live-source-ingestion.yml"


def test_wave3c_report_records_current_v32_contract() -> None:
    report = REPORT.read_text(encoding="utf-8")
    workflow = V32.read_text(encoding="utf-8")

    assert "V3_2_PRIMARY_MONITORING_OWNER_FROM_TRACKED_EVIDENCE" in report
    assert "SHARED_PATH_SEPARATE_CACHE_NAMESPACES" in report
    assert "CONFIRMED_IN_PROCESS_CONTRACT" in report
    assert "MANUAL_VERIFICATION_REQUIRED" in report
    assert "8a89b08b284461957789c8370db7375b1272597f" in report

    assert "pull_request:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "cron: '17 * * * *'" in workflow
    assert "data/monitoring/v3.2-seen-state.json" in workflow
    assert "v3.2-monitoring-state-${{ github.run_id }}" in workflow
    assert "pytest tests/test_v32_continuous_opportunity_monitoring.py -q" in workflow
    assert "v3.2-continuous-monitoring" in workflow


def test_wave3c_report_records_resolved_v37_collision_and_v33_shared_state() -> None:
    report = REPORT.read_text(encoding="utf-8")
    v37 = V37.read_text(encoding="utf-8")
    v33 = V33.read_text(encoding="utf-8")

    assert "direct V3.2/V3.7 minute-17 collision is resolved" in report
    assert "schedule:" not in v37
    assert "cron:" not in v37
    assert "data/monitoring/v3.2-seen-state.json" in v33
    assert "v3.3-auksjonen-seen-${{ runner.os }}-${{ github.run_id }}" in v33


def test_wave3c_is_documentation_only() -> None:
    report = REPORT.read_text(encoding="utf-8")

    assert "Workflow behavior changed:** none" in report
    assert "No schedule change is approved by this audit" in report
    assert "No workflow changed in this audit" in report
