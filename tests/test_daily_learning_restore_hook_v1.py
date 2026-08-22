from pathlib import Path


def test_checkpoint_restore_preserves_prior_learning_but_defers_new_cycle() -> None:
    source = Path("scripts/restore_previous_checkpoint_state.py").read_text(
        encoding="utf-8"
    )

    assert "run_daily_learning_runtime" not in source
    assert "DailyLearningPolicy" not in source
    assert 'Path("learning") / "active-keyword-overlay.json"' in source
    assert 'input_root / "learning" / "active-keyword-overlay.json"' in source
    assert 'SHADOW_KEYWORD_OVERLAY_FILENAME = "shadow-keyword-overlay.json"' in source
    assert '"daily_learning_cycle"' in source
    assert '"DEFERRED_UNTIL_POST_CAPTURE"' in source
    assert '"daily_auto_miss_learning_cli_hook"' in source
    assert '"automatic_query_activation": False' in source
    assert '"promotion_gate_enforced": True' in source
