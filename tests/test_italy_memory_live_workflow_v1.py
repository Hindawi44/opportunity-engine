from pathlib import Path

WORKFLOWS = Path(".github/workflows")
ACTIVE = WORKFLOWS / "multi-market-daily-operator-checkpoint.yaml"
ARCHIVED = Path("docs/archive/legacy-six-market-checkpoint-20260919.yaml.txt")
TESTS_WORKFLOW = WORKFLOWS / "research-shadow-manual.yaml"


def test_italy_is_not_an_automatic_market_anymore() -> None:
    workflows = sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])
    assert len(workflows) == 6
    scheduled = []
    for path in workflows:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines()
                 if not line.lstrip().startswith("#")]
        if any(line.strip() == "schedule:" for line in lines):
            scheduled.append(path.name)
    assert scheduled == ["multi-market-daily-operator-checkpoint.yaml"]
    active = ACTIVE.read_text(encoding="utf-8")
    assert "italy" not in active.casefold()
    assert "--market IT" not in active
    assert "\n  schedule:" not in TESTS_WORKFLOW.read_text(encoding="utf-8")


def test_italy_memory_and_historical_execution_are_retained_but_not_active() -> None:
    runner = Path("scripts/run_multi_market_daily_operator_checkpoint.py").read_text(encoding="utf-8")
    restore = Path("scripts/restore_previous_checkpoint_state.py").read_text(encoding="utf-8")
    old = ARCHIVED.read_text(encoding="utf-8")
    active = ACTIVE.read_text(encoding="utf-8")
    for marker in ("collect_italy_market_signals", "run_italy_case_memory_cycle",
                   "run_italy_exact_lot_verification", "run_italy_commercial_qualification",
                   "_run_italy_memory_sidecar", 'output_dir / "italy-case-memory-v1.json"',
                   'output_dir / "italy-signal-follow-up-v1.json"',
                   'output_dir / "italy-exact-lot-verification-v1.json"',
                   'output_dir / "italy-commercial-qualification-v1.json"',
                   'input_root / "it-market"'):
        assert marker in runner
    assert 'ITALY_MEMORY_RELATIVE_PATH = "it-market/opportunity_engine.db"' in restore
    assert "python scripts/restore_previous_checkpoint_state.py" in old
    assert "python scripts/run_multi_market_daily_operator_checkpoint.py" in old
    assert "run_multi_market_daily_operator_checkpoint.py" not in active
