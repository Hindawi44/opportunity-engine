from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS_WORKFLOW = ROOT / ".github/workflows/tests.yml"
DAILY = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"
WORKFLOWS = ROOT / ".github/workflows"


def test_relevant_main_pushes_dispatch_existing_live_checkpoint() -> None:
    text = TESTS_WORKFLOW.read_text(encoding="utf-8")

    assert "push:" in text
    assert "branches: [main]" in text
    assert "auto-live-checkpoint-after-main:" in text
    assert "needs: test" in text
    assert "github.event_name == 'push'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert "Detect relevant learning, memory, route or unified-search change" in text
    assert "config/learning/" in text
    assert "build_domain_market_intelligence_feed" in text
    assert "run_daily_search_success_learning" in text
    assert "run_auksjonen_live_clothing" in text
    assert "checkpoint_state_restore" in text
    assert "(learning|memory|route)" in text
    assert "actions: write" in text
    assert "contents: read" in text
    assert "multi-market-daily-operator-checkpoint.yaml" in text
    assert "/actions/workflows/${TARGET_WORKFLOW}/dispatches" in text
    assert "--data '{\"ref\":\"main\"}'" in text
    assert "git push" not in text


def test_auto_dispatch_does_not_expand_workflow_inventory() -> None:
    live = [
        path
        for path in WORKFLOWS.iterdir()
        if path.suffix in {".yml", ".yaml"}
    ]
    assert len(live) == 4
    assert not (WORKFLOWS / "auto-live-checkpoint-on-main.yaml").exists()


def test_target_live_checkpoint_still_supports_manual_and_daily_runs() -> None:
    text = DAILY.read_text(encoding="utf-8")

    assert "name: Multi-Market Daily Operator Checkpoint" in text
    assert "workflow_dispatch:" in text
    assert "schedule:" in text
    assert 'cron: "47 0-6 * * *"' in text
    assert 'timezone: "Europe/Oslo"' in text
    assert "daily-schedule-guard:" in text
    assert "needs: daily-schedule-guard" in text
    assert "needs.daily-schedule-guard.outputs.should_run == 'true'" in text
    assert "cancel-in-progress: false" in text
    assert "operator-read-only-checkpoint:" in text
    assert "production_mutation" in text
    assert "automatic_purchase" in text
    assert "automatic_payment" in text
