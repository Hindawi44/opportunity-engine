from pathlib import Path


def test_wave2a_audit_report_exists_and_preserves_scope() -> None:
    report = Path("docs/WORKFLOW_WAVE2A_PREREQUISITE_AUDIT_REPORT_v1.0.md")
    text = report.read_text(encoding="utf-8")

    assert "MANUAL_VERIFICATION_REQUIRED" in text
    assert ".github/workflows/tests.yml" in text
    assert "discovery-v1-clothing-inventory.yml" in text
    assert "discovery-v1.1-live-search.yml" in text
    assert "No file under `.github/workflows/` was modified" in text


def test_wave2a_audit_defines_exact_first_slice() -> None:
    text = Path(
        "docs/WORKFLOW_WAVE2A_PREREQUISITE_AUDIT_REPORT_v1.0.md"
    ).read_text(encoding="utf-8")

    assert "tests/test_discovery_opportunity_maps.py" in text
    assert "tests/test_discovery_classifier.py" in text
    assert "tests/test_discovery_v11_live_search.py" in text
    assert "pytest-output" in text
