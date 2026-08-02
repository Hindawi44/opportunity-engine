from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"


def test_checkpoint_workflow_is_manual_and_read_only() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "name: Multi-Market Daily Operator Checkpoint" in text
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "permissions:\n  contents: read" in text
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
