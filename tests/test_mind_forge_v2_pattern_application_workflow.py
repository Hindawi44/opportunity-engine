from pathlib import Path


WORKFLOW = Path(".github/workflows/mind-forge-pattern-application-gate.yaml")


def test_pattern_application_gate_is_manual_main_only_and_has_no_paid_execution():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "GITHUB_REF_NAME" in text
    assert "main" in text
    assert "github.actor" in text
    assert "OPENAI_API_KEY" not in text
    assert "gpt-" not in text.lower()


def test_pattern_application_gate_restores_and_saves_same_cross_run_memory_channel():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "actions/cache/restore@v4" in text
    assert "actions/cache/save@v4" in text
    assert "mind-forge-fast-memory-" in text
    assert ".mind-forge-memory/fast_learning_memory.json" in text
    assert "scripts/mind_forge_v2_pattern_application.py" in text


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

    assert "auto_apply_to_production" in text
    assert "may_auto_reject_ideas" in text
    assert "approved_production_adjustments" in text
