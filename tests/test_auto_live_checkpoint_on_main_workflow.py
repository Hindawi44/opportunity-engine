from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISPATCH_WORKFLOW = ROOT / ".github/workflows/production-dispatch-after-ci.yaml"
DAILY = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"
WORKFLOWS = ROOT / ".github/workflows"


def test_old_post_ci_dispatch_is_not_automatically_triggered() -> None:
    text = DISPATCH_WORKFLOW.read_text(encoding="utf-8")
    trigger = text.split("on:", 1)[1].split("permissions:", 1)[0]
    assert "workflow_run:" not in trigger
    assert "schedule:" not in trigger
    assert "workflow_dispatch:" in trigger
    assert "dispatch:\n    if: ${{ false }}" in text
    assert "Detect relevant production-path change" in text
    assert "actions: write" in text
    assert "contents: read" in text
    assert "multi-market-daily-operator-checkpoint.yaml" in text
    assert "/actions/workflows/${TARGET_WORKFLOW}/dispatches" in text
    assert "git push" not in text


def test_pause_does_not_expand_workflow_inventory() -> None:
    live = [path for path in WORKFLOWS.iterdir() if path.suffix in {".yml", ".yaml"}]
    assert len(live) == 6
    assert (WORKFLOWS / "production-dispatch-after-ci.yaml").exists()


def test_norway_checkpoint_is_daily_and_manual_while_event_prototype_stays_disabled() -> None:
    text = DAILY.read_text(encoding="utf-8")
    trigger = text.split("on:", 1)[1].split("permissions:", 1)[0]
    assert text.startswith("name: Norway Opportunity Hunter\n")
    assert "workflow_dispatch:" in trigger
    assert "schedule:" in trigger
    assert 'timezone: "Europe/Oslo"' in trigger
    assert "cancel-in-progress: false" in text
    assert "norway-events:\n    # Keep the audited source code and historical artifacts; do not execute events.\n    if: ${{ false }}" in text
    assert "run_event_first_hunter_pilot.py" in text
    assert "operator-read-only-checkpoint:" not in text
    assert "run_explicit_six_market_expansion.py" not in text
    for foreign in ("--market SE", "--market DE", "--market FR", "--market IT", "--market NL"):
        assert foreign not in text
