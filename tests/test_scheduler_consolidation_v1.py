from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

LEGACY_MANUAL_ONLY = (
    "daily-opportunity-pipeline.yml",
    "scheduled-agent.yml",
    "v3.2-continuous-opportunity-monitoring.yml",
    "v3.3-live-source-ingestion.yml",
    "riegermann-active-auctions-live.yaml",
    "venta-active-clothing-watch.yaml",
    "dpv-active-clothing-watch.yaml",
)

AUTOMATIC_SCHEDULE_OWNER = "multi-market-daily-operator-checkpoint.yaml"


def _text(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_legacy_schedulers_are_manual_only() -> None:
    for name in LEGACY_MANUAL_ONLY:
        workflow = _text(name)
        assert "workflow_dispatch:" in workflow, name
        assert "\n  schedule:" not in workflow, name


def test_multi_market_checkpoint_keeps_automatic_schedule() -> None:
    workflow = _text(AUTOMATIC_SCHEDULE_OWNER)
    assert "\n  schedule:" in workflow
    assert 'cron: "17 5 * * *"' in workflow
    assert "workflow_dispatch:" in workflow


def test_multi_market_checkpoint_is_the_only_live_schedule_owner() -> None:
    scheduled = []
    for path in sorted(WORKFLOWS.iterdir()):
        if path.suffix not in {".yml", ".yaml"}:
            continue
        if "\n  schedule:" in path.read_text(encoding="utf-8"):
            scheduled.append(path.name)

    assert scheduled == [AUTOMATIC_SCHEDULE_OWNER]
