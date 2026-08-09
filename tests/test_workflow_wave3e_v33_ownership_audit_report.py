from pathlib import Path


REPORT = Path("docs/WORKFLOW_WAVE3E_V33_OWNERSHIP_AUDIT_REPORT_v1.0.md")
WORKFLOW = Path(".github/workflows/v3.3-live-source-ingestion.yml")


def test_wave3e_report_documents_required_v33_contracts():
    text = REPORT.read_text(encoding="utf-8")

    required = (
        "V3.3 Live Source Ingestion Ownership Audit Report",
        ".github/workflows/v3.3-live-source-ingestion.yml",
        "V3.3 Live Source Ingestion & Snapshot Refresh",
        "auksjonen-source-ingestion",
        "12 * * * *",
        "workflow_dispatch",
        "scripts/run_v33_auksjonen_ingestion.py",
        "src/opportunity_engine/source_ingestion/auksjonen.py",
        "tests/test_v33_live_source_ingestion.py",
        "tests/fixtures/v33_auksjonen_page.html",
        "data/live_validation/v3.3-auksjonen-live-snapshot.json",
        "data/validation/v3.3-source-ingestion.json",
        "data/validation/v3.2-continuous-monitoring.json",
        "data/monitoring/v3.2-seen-state.json",
        "v3.3-auksjonen-source-ingestion",
        "scripts/run_v34_persistent_opportunity_state.py",
        "MANUAL_VERIFICATION_REQUIRED",
        "ba4f271395388b14881176b228efc211b0ea0a3f",
    )

    for fragment in required:
        assert fragment in text


def test_wave3e_report_records_shared_state_and_separate_cache_risk():
    text = REPORT.read_text(encoding="utf-8")

    assert "same logical state path" in text
    assert "different cache namespaces" in text
    assert "divergent hosted-cache copies" in text
    assert "v3.3-auksjonen-seen-${{ runner.os }}-${{ github.run_id }}" in text
    assert "v3.2-monitoring-state-" in text
    assert "does not verify cross-workflow GitHub cache synchronization" in text


def test_wave3e_report_defines_proposal_without_authorizing_change():
    text = REPORT.read_text(encoding="utf-8")

    assert "RETAIN_TEMPORARILY_PENDING_DEDICATED_IMPLEMENTATION_DECISION" in text
    assert "Wave 3E authorizes no workflow change" in text
    assert "Candidate path scope" in text
    assert "This list is a proposal, not an approved implementation in Wave 3E" in text
    assert "Do not alter shared state or separate cache namespaces" in text


def test_v33_workflow_preserves_manual_contract_after_scheduler_cleanup():
    text = WORKFLOW.read_text(encoding="utf-8")

    required = (
        "name: V3.3 Live Source Ingestion & Snapshot Refresh",
        "pull_request:",
        "branches: [ main ]",
        "paths:",
        ".github/workflows/v3.3-live-source-ingestion.yml",
        "scripts/run_v33_auksjonen_ingestion.py",
        "src/opportunity_engine/source_ingestion/auksjonen.py",
        "scripts/run_v32_continuous_opportunity_monitoring.py",
        "tests/test_v33_live_source_ingestion.py",
        "tests/fixtures/v33_auksjonen_page.html",
        "workflow_dispatch:",
        "auksjonen-source-ingestion:",
        "python-version: '3.11'",
        "path: data/monitoring/v3.2-seen-state.json",
        "key: v3.3-auksjonen-seen-${{ runner.os }}-${{ github.run_id }}",
        "pytest tests/test_v33_live_source_ingestion.py -q",
        "python scripts/run_v33_auksjonen_ingestion.py",
        "name: v3.3-auksjonen-source-ingestion",
        "data/live_validation/v3.3-auksjonen-live-snapshot.json",
        "data/validation/v3.3-source-ingestion.json",
        "data/validation/v3.2-continuous-monitoring.json",
        "if-no-files-found: warn",
    )

    for fragment in required:
        assert fragment in text

    assert "cron: '12 * * * *'" not in text
    assert "\n  schedule:" not in text
    assert "Legacy hourly scheduler retired" in text
    assert text.count("if: always()") == 3
