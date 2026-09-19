from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISPATCH_WORKFLOW = ROOT / ".github/workflows/production-dispatch-after-ci.yaml"
DAILY = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"
WORKFLOWS = ROOT / ".github/workflows"


def test_relevant_main_pushes_dispatch_existing_live_checkpoint() -> None:
    text = DISPATCH_WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_run:" in text
    assert "workflows: [Tests]" in text
    assert "branches: [main]" in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "Detect relevant production-path change" in text
    assert "actions: write" in text
    assert "contents: read" in text
    assert "multi-market-daily-operator-checkpoint.yaml" in text
    assert "/actions/workflows/${TARGET_WORKFLOW}/dispatches" in text
    assert "--data '{\"ref\":\"main\"}'" in text
    assert "git push" not in text


def test_auto_dispatch_does_not_expand_workflow_inventory() -> None:
    live = [path for path in WORKFLOWS.iterdir() if path.suffix in {".yml", ".yaml"}]
    assert len(live) == 6
    assert (WORKFLOWS / "production-dispatch-after-ci.yaml").exists()


def test_target_live_checkpoint_supports_only_norwegian_manual_and_daily_runs() -> None:
    text = DAILY.read_text(encoding="utf-8")
    assert text.startswith("name: Norway Opportunity Hunter\n")
    assert "workflow_dispatch:" in text
    assert "schedule:" in text
    assert 'cron: "47 5 * * *"' in text
    assert 'timezone: "Europe/Oslo"' in text
    assert "cancel-in-progress: false" in text
    assert "norway-events:" in text
    assert "run_event_first_hunter_pilot.py" in text
    assert "operator-read-only-checkpoint:" not in text
    assert "run_explicit_six_market_expansion.py" not in text
