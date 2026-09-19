"""Preserve original source-quality unit tests; foreign live runner is archived."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "tests/_legacy_six_market/cross_source_scent_expansion_v2.py"
ARCHIVED = ROOT / "docs/archive/legacy-six-market-checkpoint-20260919.yaml.txt"
ACTIVE = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"
spec = spec_from_file_location("archived_cross_source_scent_unit_tests", LEGACY)
assert spec is not None and spec.loader is not None
legacy = module_from_spec(spec)
spec.loader.exec_module(legacy)
legacy.ROOT = ROOT
legacy.CHECKPOINT_WORKFLOW = ARCHIVED
for name, test in vars(legacy).items():
    if name.startswith("test_") and name != "test_v2_trial_is_wired_into_existing_checkpoint_without_sixth_workflow":
        globals()[name] = test


def test_cross_source_scent_expansion_is_archived_not_in_active_norway_schedule() -> None:
    old = ARCHIVED.read_text(encoding="utf-8")
    live = ACTIVE.read_text(encoding="utf-8")
    for marker in ("run_cross_source_scent_v2:", "cross_source_scent_v2_max_requests:",
                   "Run optional cross-source scent expansion V2 trial",
                   "scripts/run_cross_source_scent_expansion_v2.py"):
        assert marker in old
        assert marker not in live
    assert live.startswith("name: Norway Opportunity Hunter\n")
    assert not (ROOT / ".github/workflows/cross-source-scent-expansion-v2.yaml").exists()
