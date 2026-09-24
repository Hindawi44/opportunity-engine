"""Preserve historical learning/SQLite restore unit coverage during Norway-only cutover."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "tests/_legacy_six_market/persistent_search_success_memory_v1.py"
ARCHIVED_WORKFLOW = ROOT / "docs/archive/legacy-six-market-checkpoint-20260919.yaml.txt"
ACTIVE = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"
spec = spec_from_file_location("archived_search_success_unit_tests", LEGACY)
assert spec is not None and spec.loader is not None
legacy = module_from_spec(spec)
spec.loader.exec_module(legacy)
legacy.ROOT = ROOT
legacy.WORKFLOW = ARCHIVED_WORKFLOW
legacy.DAILY_SCRIPT = ROOT / "scripts/run_daily_search_success_learning.py"
for name, test in vars(legacy).items():
    if name.startswith("test_") and name != "test_daily_checkpoint_wires_durable_search_success_learning":
        globals()[name] = test


def test_cross_country_search_learning_stays_archived_while_exa_returns_to_norway() -> None:
    old = ARCHIVED_WORKFLOW.read_text(encoding="utf-8")
    active = ACTIVE.read_text(encoding="utf-8")
    assert "scripts/run_daily_search_success_learning.py" in old
    assert 'EXA_API_KEY: ${{ secrets.EXA_API_KEY }}' in old
    assert "scripts/run_daily_search_success_learning.py" not in active
    norway = active.split("  norway-all-assets:\n", 1)[1].split("  norway-existing-engine:\n", 1)[0]
    assert 'EXA_API_KEY: ${{ secrets.EXA_API_KEY }}' in norway
    assert "run_exa_exact_lot_checkpoint.py" in norway
    assert "--market NO" in norway
    for foreign in ("--market SE", "--market DE", "--market FR", "--market IT", "--market NL"):
        assert foreign not in active
    assert "run_event_first_hunter_pilot.py" in active
