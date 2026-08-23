from pathlib import Path


WORKFLOW = Path(".github/workflows/mind-forge-live-research-launcher.yaml")


def test_launcher_restores_latest_fast_memory_before_live_cycle():
    assert WORKFLOW.is_file()
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "actions/cache/restore@v4" in text
    assert "mind-forge-fast-memory-" in text
    assert ".mind-forge-memory" in text
    assert "MIND_FORGE_PRIOR_MEMORY_PATH" in text
    restore_pos = text.index("actions/cache/restore@v4")
    run_pos = text.index("Run one autonomous MIND FORGE V2 cycle from the raw seed")
    assert restore_pos < run_pos


def test_launcher_saves_current_fast_memory_after_success_for_next_run():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "fast_learning_memory.json" in text
    assert "actions/cache/save@v4" in text
    assert "mind-forge-fast-memory-${{ github.run_id }}" in text
    assert text.index("fast_learning_memory.json") < text.rindex("actions/cache/save@v4")


def test_cross_run_memory_does_not_create_schedule_or_remove_paid_confirmation():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "schedule:" not in text
    assert "confirm_paid_live_research:" in text
    assert "inputs.confirm_paid_live_research == 'YES'" in text
    assert "MIND_FORGE_LIVE_ENABLED: \"1\"" in text
