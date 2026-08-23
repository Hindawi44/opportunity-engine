from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTO = ROOT / ".github/workflows/auto-live-checkpoint-on-main.yaml"
DAILY = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"


def test_relevant_main_pushes_dispatch_existing_live_checkpoint() -> None:
    text = AUTO.read_text(encoding="utf-8")

    assert "name: Auto Live Checkpoint On Main" in text
    assert "push:" in text
    assert "branches:\n      - main" in text
    assert '"config/learning/**"' in text
    assert '"src/opportunity_engine/**/*learning*.py"' in text
    assert '"src/opportunity_engine/**/*memory*.py"' in text
    assert '"src/opportunity_engine/**/*route*.py"' in text
    assert '"src/opportunity_engine/discovery/checkpoint_state_restore.py"' in text
    assert '"src/opportunity_engine/discovery/domain_market_intelligence_feed.py"' in text
    assert "actions: write" in text
    assert "contents: read" in text
    assert "multi-market-daily-operator-checkpoint.yaml" in text
    assert "/actions/workflows/${TARGET_WORKFLOW}/dispatches" in text
    assert "--data '{\"ref\":\"main\"}'" in text
    assert "git push" not in text


def test_target_live_checkpoint_still_supports_manual_dispatch() -> None:
    text = DAILY.read_text(encoding="utf-8")

    assert "name: Multi-Market Daily Operator Checkpoint" in text
    assert "workflow_dispatch:" in text
    assert "operator-read-only-checkpoint:" in text
    assert "production_mutation" in text
    assert "automatic_purchase" in text
    assert "automatic_payment" in text
