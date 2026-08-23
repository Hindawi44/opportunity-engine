from pathlib import Path


WORKFLOW = Path(".github/workflows/mind-forge-live-research-launcher.yaml")
SEPARATE_WORKFLOW = Path(".github/workflows/mind-forge-pattern-application-gate.yaml")


def _gate_job(text: str) -> str:
    return text.split("  pattern-application-gate:", 1)[1].split("  creative-v2-open-live:", 1)[0]


def test_pattern_application_gate_reuses_existing_manual_launcher_and_is_main_only():
    text = WORKFLOW.read_text(encoding="utf-8")
    gate = _gate_job(text)

    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert SEPARATE_WORKFLOW.exists() is False
    assert "operation:" in text
    assert "default: RUN_SEED" in text
    assert "inputs.operation != 'RUN_SEED'" in gate
    assert "GITHUB_REF_NAME" in gate
    assert "main" in gate
    assert "github.actor" in gate
    assert "OPENAI_API_KEY" not in gate
    assert "gpt-" not in gate.lower()


def test_pattern_application_gate_restores_and_saves_same_cross_run_memory_channel():
    text = WORKFLOW.read_text(encoding="utf-8")
    gate = _gate_job(text)

    assert "actions/cache/restore@v4" in gate
    assert "actions/cache/save@v4" in gate
    assert "mind-forge-fast-memory-" in gate
    assert ".mind-forge-memory/fast_learning_memory.json" in gate
    assert "scripts/mind_forge_v2_pattern_application.py" in gate


def test_pattern_application_gate_exposes_approve_and_rollback_actions_with_explicit_ids():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "APPROVE_PATTERN" in text
    assert "ROLLBACK_PATTERN" in text
    assert "pattern_code:" in text
    assert "application_id:" in text
    assert "rollback_id:" in text
    assert "observed_independent_run_count:" in text
    assert "observed_example_diversity_count:" in text


def test_pattern_application_gate_validates_no_auto_reject_and_no_auto_apply():
    text = WORKFLOW.read_text(encoding="utf-8")
    gate = _gate_job(text)

    assert "auto_apply_to_production" in gate
    assert "may_auto_reject_ideas" in gate
    assert "approved_production_adjustments" in gate


def test_paid_seed_execution_remains_explicit_and_separate_from_pattern_gate():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "inputs.operation == 'RUN_SEED' && inputs.confirm_paid_live_research == 'YES'" in text
    assert "inputs.operation == 'RUN_SEED' && inputs.confirm_paid_live_research != 'YES'" in text
