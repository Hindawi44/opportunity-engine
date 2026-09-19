from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
SCHEDULE_OWNER = "multi-market-daily-operator-checkpoint.yaml"


def test_all_legacy_automatic_schedules_are_paused() -> None:
    scheduled = []
    for path in sorted(WORKFLOWS.iterdir()):
        if path.suffix not in {".yml", ".yaml"}:
            continue
        if "\n  schedule:" in path.read_text(encoding="utf-8"):
            scheduled.append(path.name)
    assert scheduled == []
    active = (WORKFLOWS / SCHEDULE_OWNER).read_text(encoding="utf-8")
    assert active.startswith("name: Norway Opportunity Hunter\n")
    assert "workflow_dispatch:" not in active
    assert "cancel-in-progress: false" in active
    assert "norway-events:\n    # Keep the audited source code and historical artifacts; do not execute events.\n    if: ${{ false }}" in active
