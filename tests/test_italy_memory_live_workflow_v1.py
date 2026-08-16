from pathlib import Path


def test_italy_memory_runs_daily_without_creating_sixth_workflow() -> None:
    workflow_dir = Path(".github/workflows")
    workflow_files = sorted(
        [*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")]
    )
    assert len(workflow_files) == 5

    text = (workflow_dir / "tests.yml").read_text(encoding="utf-8")
    assert 'cron: "47 5 * * *"' in text
    assert "github.event_name != 'schedule'" in text
    assert "github.event_name == 'schedule'" in text


def test_italy_live_job_restores_runs_and_uploads_durable_memory() -> None:
    text = Path(".github/workflows/tests.yml").read_text(encoding="utf-8")

    assert "Validate Italy discovery and memory contracts" in text
    assert "tests/test_italy_case_memory_adapter_v1.py" in text
    assert "tests/test_italy_case_memory_restore_v1.py" in text
    assert "scripts/run_italy_case_memory_live.py" in text
    assert "GITHUB_TOKEN: ${{ github.token }}" in text
    assert "GITHUB_REPOSITORY: ${{ github.repository }}" in text
    assert "GITHUB_RUN_ID: ${{ github.run_id }}" in text
    assert "--state-root artifacts/italy-case-memory" in text
    assert "name: italy-case-memory-v1" in text
    assert "path: artifacts/italy-case-memory/" in text
    assert "actions: read" in text
