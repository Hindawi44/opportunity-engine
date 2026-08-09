from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
ARCHIVE = ROOT / "docs" / "workflow-archive"
CHECKPOINT = WORKFLOWS / "multi-market-daily-operator-checkpoint.yaml"

ARCHIVED_SOURCES = {
    "riegermann-active-auctions-live.yaml": "scripts/run_riegermann_active_discovery.py",
    "venta-active-clothing-watch.yaml": "scripts/run_venta_active_discovery.py",
    "dpv-active-clothing-watch.yaml": "scripts/run_dpv_active_discovery.py",
}


def test_redundant_german_source_workflows_are_archived() -> None:
    for name in ARCHIVED_SOURCES:
        assert not (WORKFLOWS / name).exists(), name
        assert (ARCHIVE / name).exists(), name


def test_checkpoint_owns_archived_source_execution() -> None:
    text = CHECKPOINT.read_text(encoding="utf-8")
    for script in ARCHIVED_SOURCES.values():
        assert script in text


def test_remaining_country_diagnostics_are_manual_only() -> None:
    for name in (
        "sweden-clothing-inventory-live.yaml",
        "germany-clothing-inventory-live.yaml",
    ):
        text = (WORKFLOWS / name).read_text(encoding="utf-8")
        assert "workflow_dispatch:" in text
        assert "\n  pull_request:" not in text
        assert "\n  schedule:" not in text
