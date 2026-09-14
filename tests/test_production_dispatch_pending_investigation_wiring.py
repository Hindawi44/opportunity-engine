from pathlib import Path


def test_pending_investigation_script_is_a_production_dispatch_path() -> None:
    workflow = Path(
        ".github/workflows/production-dispatch-after-ci.yaml"
    ).read_text(encoding="utf-8")
    assert "run_pending_opportunity_investigation\\.py" in workflow
