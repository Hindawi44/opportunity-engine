import json
from pathlib import Path

import opportunity_engine.discovery.ai_teaching_gate_cli_hook as hook


DISCOVERY_INIT = Path("src/opportunity_engine/discovery/__init__.py")
HOOK = Path("src/opportunity_engine/discovery/ai_teaching_gate_cli_hook.py")
GATE = Path("src/opportunity_engine/ai_teaching_gate_v1.py")


def test_teaching_gate_runs_after_spine_memory_portfolio_and_before_learning_layer():
    source = DISCOVERY_INIT.read_text(encoding="utf-8")

    learning = source.index("install_learning_layer_review_cli_hook()")
    teaching = source.index("install_ai_teaching_gate_cli_hook()")
    spine = source.index("install_unified_learning_spine_cli_hook()")

    # atexit is LIFO, so registration order Learning -> Teaching -> Spine means
    # runtime Spine/Memory/Portfolio -> Teaching -> Learning.
    assert learning < teaching < spine


def test_teaching_gate_hook_never_imports_agents_or_calls_openai():
    source = HOOK.read_text(encoding="utf-8")
    gate_source = GATE.read_text(encoding="utf-8")

    assert "from agents" not in source
    assert "import agents" not in source
    assert "OPENAI_API_KEY" not in source
    assert "Runner.run" not in source
    assert "from agents" not in gate_source
    assert "OPENAI_API_KEY" not in gate_source
    assert '"automatic_ai_invocation": False' in source
    assert '"manual_paid_run_required": True' in source


def test_teaching_gate_consumes_existing_memory_and_route_portfolio_artifacts():
    source = HOOK.read_text(encoding="utf-8")

    assert "UNIFIED_MEMORY_FILENAME" in source
    assert "PORTFOLIO_OUTPUT_FILENAME" in source
    assert "write_ai_teaching_gate_v1" in source
    assert "ai_teaching_gate_v1:" in source


def test_teaching_gate_reads_memory_from_durable_learning_root(tmp_path, monkeypatch):
    output = tmp_path / "multi-market-daily-operator-checkpoint"
    input_root = tmp_path / "multi-market-inputs"
    learning = input_root / "learning"
    output.mkdir(parents=True)
    learning.mkdir(parents=True)

    memory = {"sentinel": "durable-memory"}
    portfolio = {"sentinel": "portfolio"}
    (learning / hook.UNIFIED_MEMORY_FILENAME).write_text(
        json.dumps(memory), encoding="utf-8"
    )
    (output / hook.PORTFOLIO_OUTPUT_FILENAME).write_text(
        json.dumps(portfolio), encoding="utf-8"
    )

    captured = {}

    def fake_writer(output_dir, *, unified_memory, market_route_portfolio):
        captured["output_dir"] = Path(output_dir)
        captured["memory"] = unified_memory
        captured["portfolio"] = market_route_portfolio
        return {"status": "SUCCESS"}

    monkeypatch.setattr(hook, "write_ai_teaching_gate_v1", fake_writer)

    report = hook.run_ai_teaching_gate_v1_fail_closed(
        output,
        input_root=input_root,
    )

    assert report["status"] == "SUCCESS"
    assert captured["memory"] == memory
    assert captured["portfolio"] == portfolio
    assert captured["output_dir"] == output


def test_gate_reuses_existing_mind_forge_runtime_and_learning_instead_of_rebuilding_them():
    source = GATE.read_text(encoding="utf-8")

    assert "mind-forge-live/phase1/live_model_adapter_v1.py" in source
    assert "scripts/mind_forge_v2_fast_learning_memory.py" in source
    assert '"existing_runtime_reused": True' in source
    assert '"existing_cross_run_learning_reused": True' in source
    assert '"budget_policy_is_not_duplicated_here": True' in source
