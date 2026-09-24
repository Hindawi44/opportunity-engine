from pathlib import Path

WORKFLOWS = Path(".github/workflows")
ACTIVE = WORKFLOWS / "multi-market-daily-operator-checkpoint.yaml"
ARCHIVED = Path("docs/archive/legacy-six-market-checkpoint-20260919.yaml.txt")
OLD_MANUAL = Path("docs/archive/foreign-manual-research-20260919.yaml.txt")
TESTS_WORKFLOW = WORKFLOWS / "research-shadow-manual.yaml"


def test_france_does_not_add_an_automatic_schedule() -> None:
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
    assert active.startswith("name: Norway Opportunity Hunter\n")
    assert "--market FR" not in active
    assert "france-market-discovery" not in active


def test_france_state_and_execution_contract_are_historical_only() -> None:
    runner = Path("scripts/run_multi_market_daily_operator_checkpoint.py").read_text(encoding="utf-8")
    restore = Path("scripts/restore_previous_checkpoint_state.py").read_text(encoding="utf-8")
    manual = TESTS_WORKFLOW.read_text(encoding="utf-8")
    old_manual = OLD_MANUAL.read_text(encoding="utf-8")
    old = ARCHIVED.read_text(encoding="utf-8")
    active = ACTIVE.read_text(encoding="utf-8")
    for marker in ("collect_france_market_signals", "run_france_case_memory_cycle", "_run_france_memory_sidecar",
                   'input_root / "fr-market"', 'output_dir / "france-market-discovery-v1.json"',
                   'output_dir / "france-case-memory-v1.json"', 'output_dir / "france-signal-follow-up-v1.json"'):
        assert marker in runner
    assert 'FRANCE_MEMORY_RELATIVE_PATH = "fr-market/opportunity_engine.db"' in restore
    assert "france-market-discovery-live:" in old_manual
    assert "france-market-discovery-live:" not in manual
    assert "python scripts/restore_previous_checkpoint_state.py" in old
    assert "python scripts/run_multi_market_daily_operator_checkpoint.py" in old
    assert "run_multi_market_daily_operator_checkpoint.py" not in active
    assert "france-market-discovery" not in active
