from pathlib import Path


WORKFLOWS = Path(".github/workflows")
CHECKPOINT = WORKFLOWS / "multi-market-daily-operator-checkpoint.yaml"
TESTS_WORKFLOW = WORKFLOWS / "tests.yml"


def test_netherlands_reuses_the_only_existing_schedule_owner() -> None:
    workflow_files = sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])
    assert len(workflow_files) == 5

    scheduled = []
    for path in workflow_files:
        text = path.read_text(encoding="utf-8")
        live_lines = [
            line for line in text.splitlines() if not line.lstrip().startswith("#")
        ]
        if any(line.strip() == "schedule:" for line in live_lines):
            scheduled.append(path.name)
    assert scheduled == ["multi-market-daily-operator-checkpoint.yaml"]
    assert "\n  schedule:" not in TESTS_WORKFLOW.read_text(encoding="utf-8")


def test_checkpoint_runner_owns_netherlands_sidecar_without_changing_canonical_coverage() -> None:
    runner = Path("scripts/run_multi_market_daily_operator_checkpoint.py").read_text(
        encoding="utf-8"
    )
    restore = Path("scripts/restore_previous_checkpoint_state.py").read_text(
        encoding="utf-8"
    )
    workflow = CHECKPOINT.read_text(encoding="utf-8")

    assert "collect_netherlands_market_signals" in runner
    assert "run_netherlands_case_memory_cycle" in runner
    assert "_run_netherlands_memory_sidecar" in runner
    assert '"canonical_market_coverage_unchanged": ["NO", "SE", "DE"]' in runner
    assert 'output_dir / "netherlands-market-discovery-v1.json"' in runner
    assert 'output_dir / "netherlands-case-memory-v1.json"' in runner
    assert 'output_dir / "netherlands-signal-follow-up-v1.json"' in runner
    assert 'input_root / "nl-market"' in runner
    assert '"NOT_BUILT_YET_REQUIRES_SOURCE_SPECIFIC_VALIDATION"' in runner

    assert 'NETHERLANDS_MEMORY_RELATIVE_PATH = "nl-market/opportunity_engine.db"' in restore
    assert "checkpoint_state_restore.DATABASE_RELATIVE_PATHS" in restore

    assert "python scripts/restore_previous_checkpoint_state.py" in workflow
    assert "python scripts/run_multi_market_daily_operator_checkpoint.py" in workflow
    assert "artifacts/multi-market-daily-operator-checkpoint/" in workflow
    assert "artifacts/multi-market-inputs/" in workflow
