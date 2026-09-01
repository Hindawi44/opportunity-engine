from pathlib import Path


WORKFLOWS = Path(".github/workflows")
CHECKPOINT = WORKFLOWS / "multi-market-daily-operator-checkpoint.yaml"
TESTS_WORKFLOW = WORKFLOWS / "research-shadow-manual.yaml"


def test_italy_memory_reuses_the_only_existing_schedule_owner() -> None:
    workflow_files = sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])
    assert len(workflow_files) == 6

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


def test_canonical_checkpoint_runner_owns_italy_sidecar_without_changing_coverage() -> None:
    runner = Path("scripts/run_multi_market_daily_operator_checkpoint.py").read_text(
        encoding="utf-8"
    )
    restore = Path("scripts/restore_previous_checkpoint_state.py").read_text(
        encoding="utf-8"
    )
    workflow = CHECKPOINT.read_text(encoding="utf-8")

    assert "collect_italy_market_signals" in runner
    assert "run_italy_case_memory_cycle" in runner
    assert "run_italy_exact_lot_verification" in runner
    assert "run_italy_commercial_qualification" in runner
    assert "_run_italy_memory_sidecar" in runner
    assert '"canonical_market_coverage_unchanged": ["NO", "SE", "DE"]' in runner
    assert 'output_dir / "italy-case-memory-v1.json"' in runner
    assert 'output_dir / "italy-signal-follow-up-v1.json"' in runner
    assert 'output_dir / "italy-exact-lot-verification-v1.json"' in runner
    assert 'output_dir / "italy-commercial-qualification-v1.json"' in runner
    assert 'input_root / "it-market"' in runner

    assert 'ITALY_MEMORY_RELATIVE_PATH = "it-market/opportunity_engine.db"' in restore
    assert "checkpoint_state_restore.DATABASE_RELATIVE_PATHS" in restore

    assert "python scripts/restore_previous_checkpoint_state.py" in workflow
    assert "python scripts/run_multi_market_daily_operator_checkpoint.py" in workflow
    assert "artifacts/multi-market-daily-operator-checkpoint/" in workflow
    assert "artifacts/multi-market-inputs/" in workflow
