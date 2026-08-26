from pathlib import Path


WORKFLOWS = Path(".github/workflows")
CHECKPOINT = WORKFLOWS / "multi-market-daily-operator-checkpoint.yaml"
TESTS_WORKFLOW = WORKFLOWS / "tests.yml"


def test_france_reuses_existing_schedule_and_does_not_add_scheduler() -> None:
    workflow_files = sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])
    assert len(workflow_files) == 4
    scheduled = []
    for path in workflow_files:
        live_lines = [
            line for line in path.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("#")
        ]
        if any(line.strip() == "schedule:" for line in live_lines):
            scheduled.append(path.name)
    assert scheduled == ["multi-market-daily-operator-checkpoint.yaml"]


def test_daily_runner_and_restore_include_france_sidecar() -> None:
    runner = Path("scripts/run_multi_market_daily_operator_checkpoint.py").read_text(
        encoding="utf-8"
    )
    restore = Path("scripts/restore_previous_checkpoint_state.py").read_text(
        encoding="utf-8"
    )
    tests_workflow = TESTS_WORKFLOW.read_text(encoding="utf-8")
    checkpoint = CHECKPOINT.read_text(encoding="utf-8")

    assert "collect_france_market_signals" in runner
    assert "run_france_case_memory_cycle" in runner
    assert "_run_france_memory_sidecar" in runner
    assert 'input_root / "fr-market"' in runner
    assert 'output_dir / "france-market-discovery-v1.json"' in runner
    assert 'output_dir / "france-case-memory-v1.json"' in runner
    assert 'output_dir / "france-signal-follow-up-v1.json"' in runner
    assert '"market_role": "OFFICIAL_EXPANSION_MARKET"' in runner
    assert '"canonical_market_coverage_unchanged": ["NO", "SE", "DE"]' in runner

    assert 'FRANCE_MEMORY_RELATIVE_PATH = "fr-market/opportunity_engine.db"' in restore
    assert "FRANCE_MEMORY_RELATIVE_PATH" in restore

    assert "france-market-discovery-live:" in tests_workflow
    assert "France market discovery live validation" in tests_workflow
    assert "test_france_market_discovery_v1.py" in tests_workflow
    assert "test_france_case_memory_adapter_v1.py" in tests_workflow

    assert "python scripts/restore_previous_checkpoint_state.py" in checkpoint
    assert "python scripts/run_multi_market_daily_operator_checkpoint.py" in checkpoint
    assert "artifacts/multi-market-daily-operator-checkpoint/" in checkpoint
    assert "artifacts/multi-market-inputs/" in checkpoint
