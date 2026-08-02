from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "riegermann-active-auctions-live.yaml"


def test_riegermann_active_workflow_runs_daily_and_keeps_manual_dispatch() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "schedule:" in workflow
    assert '- cron: "17 5 * * *"' in workflow
    assert "workflow_dispatch:" in workflow
    assert "pull_request:" in workflow


def test_scheduled_riegermann_run_uses_safe_persistent_defaults() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "github.event_name != 'workflow_dispatch' || inputs.persist_unified" in workflow
    assert "github.event.inputs.auction_limit || '5'" in workflow
    assert "github.event.inputs.catalog_page_limit || '100'" in workflow
    assert "github.event.inputs.item_verification_limit || '10'" in workflow
    assert "--persist-unified" in workflow
    assert "--database-url" in workflow
