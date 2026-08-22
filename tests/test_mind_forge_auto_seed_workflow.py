from pathlib import Path


WORKFLOW = Path('.github/workflows/mind-forge-auto-seed.yaml')


def test_auto_launcher_accepts_raw_seed_without_manual_execution_mode():
    text = WORKFLOW.read_text(encoding='utf-8')

    assert 'seed:' in text
    assert 'confirm_paid_execution:' in text
    assert 'mode:' not in text.split('workflow_dispatch:', 1)[1].split('permissions:', 1)[0]
    assert 'AUTO_ROUTE=CREATIVE_V2_OPEN' in text
    assert 'mode: "CREATIVE_V2_OPEN"' in text


def test_auto_launcher_preserves_explicit_paid_authorization_and_no_silent_execution():
    text = WORKFLOW.read_text(encoding='utf-8')

    assert 'default: "NO"' in text
    assert "inputs.confirm_paid_execution == 'YES'" in text
    assert "inputs.confirm_paid_execution != 'YES'" in text
    assert 'actions: write' in text


def test_auto_launcher_dispatches_current_main_launcher_not_a_feature_branch():
    text = WORKFLOW.read_text(encoding='utf-8')

    assert '--arg ref "main"' in text
    assert 'mind-forge-live-research-launcher.yaml/dispatches' in text
