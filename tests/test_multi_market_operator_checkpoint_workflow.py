from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"


def test_checkpoint_workflow_is_manual_and_read_only() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "name: Multi-Market Daily Operator Checkpoint" in text
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "permissions:\n  contents: read\n  actions: read" in text
    assert "automatic_purchase" in text
    assert "automatic_payment" in text
    assert "run_multi_market_daily_operator_checkpoint.py" in text


def test_checkpoint_workflow_covers_only_completed_markets() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert '"market_code": "NO"' in text
    assert '"market_code": "SE"' in text
    assert '"market_code": "DE"' in text
    assert '"market_code": "DK"' not in text
    assert "run_auksjonen_live_clothing.py" in text
    assert "--market SE" in text
    assert "run_riegermann_active_discovery.py" in text
    assert "run_venta_active_discovery.py" in text
    assert "run_dpv_active_discovery.py" in text


def test_checkpoint_workflow_preserves_one_human_action() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'summary.count("الإجراء البشري الوحيد:") != 1' in text
    assert "contact sellers" not in text.lower()
    assert "git push" not in text


def test_checkpoint_restores_state_before_sources_and_enriches_after_build() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    restore = text.index("- name: Restore previous lifecycle SQLite state")
    first_source = text.index("- name: Run Norway Auksjonen public clothing path")
    build = text.index("- name: Build the three-market operator checkpoint")
    enrich = text.index("- name: Enrich checkpoint with lifecycle state and transitions")

    assert restore < first_source < build < enrich
    assert "previous-state-restore.json" in text
    assert "SINCE_PREVIOUS_SUCCESSFUL_CHECKPOINT" in text
    assert "CURRENT_RUN_INITIALIZATION" in text
    assert "دورة الحياة:" in text
    assert "استمرارية SQLite:" in text


def test_checkpoint_persists_and_validates_auksjonen_lifecycle() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    start = text.index("Run Norway Auksjonen public clothing path")
    end = text.index("Run Sweden Blinto bounded pilot", start)
    norway_step = text[start:end]

    assert "--persist-unified" in norway_step
    assert (
        'sqlite:///$INPUT_ROOT/no-auksjonen/opportunity_engine.db' in norway_step
    )
    assert "Auksjonen unified SQLite persistence did not succeed" in text
    assert "Auksjonen lifecycle event storage is not enabled" in text
