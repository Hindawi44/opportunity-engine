from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.discovery import checkpoint_state_restore
from opportunity_engine.discovery import commercial_anchor_outcome_learning_cli_hook as hook
from opportunity_engine.discovery.commercial_anchor_outcome_learning import (
    MEMORY_FILENAME,
    OUTPUT_FILENAME,
)


ROOT = Path(__file__).resolve().parents[1]


def test_run_multi_cli_registers_one_read_only_anchor_learning_callback(monkeypatch) -> None:
    registered = []
    monkeypatch.setattr(hook, "_INSTALLED", False)
    monkeypatch.setattr(hook.sys, "argv", ["scripts/run_multi_market_daily_operator_checkpoint.py"])
    monkeypatch.setattr(hook.atexit, "register", lambda callback: registered.append(callback))

    assert hook.install_commercial_anchor_outcome_learning_cli_hook() is True
    assert registered == [hook._run_anchor_outcome_learning]


def test_restore_cli_extends_only_explicit_learning_state_allowlist(monkeypatch) -> None:
    original = ("search-success-memory.json", "missed-opportunities.json")
    monkeypatch.setattr(checkpoint_state_restore, "LEARNING_STATE_FILENAMES", original)
    monkeypatch.setattr(hook, "_INSTALLED", False)
    monkeypatch.setattr(hook.sys, "argv", ["scripts/restore_previous_checkpoint_state.py"])

    assert hook.install_commercial_anchor_outcome_learning_cli_hook() is True
    assert checkpoint_state_restore.LEARNING_STATE_FILENAMES == (*original, MEMORY_FILENAME)


def test_unrelated_cli_does_not_install_anchor_learning(monkeypatch) -> None:
    registered = []
    monkeypatch.setattr(hook, "_INSTALLED", False)
    monkeypatch.setattr(hook.sys, "argv", ["pytest"])
    monkeypatch.setattr(hook.atexit, "register", lambda callback: registered.append(callback))

    assert hook.install_commercial_anchor_outcome_learning_cli_hook() is False
    assert registered == []


def test_registration_order_runs_unified_search_runtime_before_anchor_learning() -> None:
    source = (ROOT / "src/opportunity_engine/discovery/__init__.py").read_text(encoding="utf-8")
    learner = source.index("install_commercial_anchor_outcome_learning_cli_hook()\n")
    runtime = source.index("install_unified_search_runtime_cli_hook()\n")

    # atexit is LIFO: learner registered first means runtime executes first.
    assert learner < runtime


def test_callback_writes_valid_zero_without_search_when_no_resolution_exists(
    tmp_path: Path, monkeypatch
) -> None:
    input_root = tmp_path / "inputs"
    output_dir = tmp_path / "output"
    monkeypatch.setenv("INPUT_ROOT", str(input_root))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("GITHUB_RUN_ID", "live-wiring-test")

    hook._run_anchor_outcome_learning()

    report = json.loads((output_dir / OUTPUT_FILENAME).read_text(encoding="utf-8"))
    memory = json.loads(
        (input_root / "learning" / MEMORY_FILENAME).read_text(encoding="utf-8")
    )
    assert report["status"] == "VALID_ZERO"
    assert memory["status"] == "VALID_ZERO"
    assert report["current_run_observation_count"] == 0
    assert report["automatic_query_activation"] is False
    assert report["production_mutation"] is False
