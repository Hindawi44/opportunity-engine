from pathlib import Path


def test_checkpoint_restore_prepares_daily_learning_before_discovery() -> None:
    source = Path("scripts/restore_previous_checkpoint_state.py").read_text(
        encoding="utf-8"
    )

    assert "run_daily_learning_runtime" in source
    assert "DailyLearningPolicy" in source
    assert "max_candidates_per_run=2" in source
    assert 'Path("learning") / "active-keyword-overlay.json"' in source
    assert 'Path(args.input_root) / "learning"' in source
    assert '"daily_learning_cycle"' in source
