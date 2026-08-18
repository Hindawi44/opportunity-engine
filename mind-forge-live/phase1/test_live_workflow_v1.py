from pathlib import Path


WORKFLOW = Path(".github/workflows/mind-forge-live-model-v1.yaml")


def test_live_model_workflow_is_manual_only_and_explicitly_authorized():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "confirm_paid_live_run:" in text
    assert "if: ${{ inputs.confirm_paid_live_run == 'YES' }}" in text
    assert "default: \"NO\"" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "\n  schedule:" not in text


def test_live_model_workflow_reuses_existing_secret_without_exposing_value():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}" in text
    assert "value not displayed" in text
    assert "MIND_FORGE_LIVE_ENABLED: \"1\"" in text
    assert "sk-" not in text


def test_live_model_workflow_has_budget_and_model_gates():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "max_estimated_cost_usd:" in text
    assert 'default: "0.10"' in text
    assert "if int(usage[\"requests\"]) > 11:" in text
    assert "gpt-5.6-terra" in text
    assert "gpt-5.6-luna" in text
    assert "live_research_enabled\"] is not False" in text
