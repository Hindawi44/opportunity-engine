from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "WORKFLOW_CONSOLIDATION_AUDIT_V3.md"
WORKFLOWS = ROOT / ".github" / "workflows"


def test_audit_names_every_current_workflow() -> None:
    report = REPORT.read_text(encoding="utf-8")
    workflow_names = sorted(
        path.name
        for path in WORKFLOWS.iterdir()
        if path.suffix in {".yml", ".yaml"}
    )

    missing = [name for name in workflow_names if f"`{name}`" not in report]
    assert missing == []


def test_audit_keeps_one_automatic_owner_and_cross_source_reuse_boundary() -> None:
    report = REPORT.read_text(encoding="utf-8")

    assert "single automatic production scheduler" in report
    assert "multi-market-daily-operator-checkpoint.yaml" in report
    assert "scripts/run_cross_source_clothing_verification.py" in report
    assert "checkpoint-compatible adapter/report contract" in report
    assert "V1.2 remains manual" in report
    assert "NO/SE/DE only" in report
