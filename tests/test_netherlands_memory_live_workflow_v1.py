from pathlib import Path

WORKFLOWS = Path(".github/workflows")
ACTIVE = WORKFLOWS / "multi-market-daily-operator-checkpoint.yaml"
ARCHIVED = Path("docs/archive/legacy-six-market-checkpoint-20260919.yaml.txt")
OLD_MANUAL = Path("docs/archive/foreign-manual-research-20260919.yaml.txt")
MANUAL = WORKFLOWS / "research-shadow-manual.yaml"


def test_netherlands_is_not_in_an_automatic_runtime() -> None:
    workflows = sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])
    assert len(workflows) == 6
    scheduled = [path.name for path in workflows if any(
        line.strip() == "schedule:" for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#"))]
    assert scheduled == ["multi-market-daily-operator-checkpoint.yaml"]
    active = ACTIVE.read_text(encoding="utf-8")
    assert "--market NL" not in active
    assert active.startswith("name: Norway Opportunity Hunter\n")
    assert "run_explicit_six_market_expansion.py" not in active
    assert "netherlands" not in active.casefold()
    assert "\n  schedule:" not in MANUAL.read_text(encoding="utf-8")


def test_netherlands_memory_and_legacy_evidence_remain_readable() -> None:
    runner = Path("scripts/run_multi_market_daily_operator_checkpoint.py").read_text(encoding="utf-8")
    restore = Path("scripts/restore_previous_checkpoint_state.py").read_text(encoding="utf-8")
    old = ARCHIVED.read_text(encoding="utf-8")
    old_manual = OLD_MANUAL.read_text(encoding="utf-8")
    manual = MANUAL.read_text(encoding="utf-8")
    adapter = Path("src/opportunity_engine/discovery/netherlands_case_memory_adapter.py").read_text(encoding="utf-8")
    pending_cycle = Path("src/opportunity_engine/discovery/netherlands_identity_pending_cycle.py").read_text(encoding="utf-8")
    pending_memory = Path("src/opportunity_engine/discovery/netherlands_identity_pending_memory.py").read_text(encoding="utf-8")
    for marker in ("collect_netherlands_market_signals", "netherlands_identity_pending_cycle",
                   "run_netherlands_case_memory_cycle", "_run_netherlands_memory_sidecar",
                   'output_dir / "netherlands-market-discovery-v1.json"',
                   'output_dir / "netherlands-case-memory-v1.json"',
                   'output_dir / "netherlands-identity-pending-v1.json"',
                   'output_dir / "netherlands-signal-follow-up-v1.json"',
                   'input_root / "nl-market"'):
        assert marker in runner
    assert "resolve_netherlands_entity_identities" in adapter
    assert "IDENTITY_PENDING" in pending_memory
    assert "MarketSignalRepository" in pending_memory
    assert "load_identity_pending_signals" in pending_cycle
    assert "pending_is_not_follow_up_eligible" in pending_cycle
    assert "test_netherlands_entity_identity_resolution_v1.py" in old_manual
    assert "test_netherlands_entity_identity_resolution_v1.py" not in manual
    assert 'NETHERLANDS_MEMORY_RELATIVE_PATH = "nl-market/opportunity_engine.db"' in restore
    assert "python scripts/restore_previous_checkpoint_state.py" in old
    assert "python scripts/run_multi_market_daily_operator_checkpoint.py" in old
