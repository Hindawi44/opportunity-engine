from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
SCHEDULE_OWNER = "multi-market-daily-operator-checkpoint.yaml"


def test_only_norway_hunter_owns_an_automatic_schedule() -> None:
    scheduled = []
    for path in sorted(WORKFLOWS.iterdir()):
        if path.suffix not in {".yml", ".yaml"}:
            continue
        if "\n  schedule:" in path.read_text(encoding="utf-8"):
            scheduled.append(path.name)
    assert scheduled == [SCHEDULE_OWNER]
    active = (WORKFLOWS / SCHEDULE_OWNER).read_text(encoding="utf-8")
    assert active.startswith("name: Norway Opportunity Hunter\n")
    assert 'cron: "47 5 * * *"' in active
    assert 'timezone: "Europe/Oslo"' in active
    assert "workflow_dispatch:" in active
    assert "cancel-in-progress: false" in active
