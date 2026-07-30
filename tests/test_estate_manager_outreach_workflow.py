from pathlib import Path


WORKFLOW = Path(".github/workflows/daily-opportunity-pipeline.yml")


def test_daily_workflow_builds_outreach_review_packets() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "run_estate_manager_outreach_review.py" in text
    assert "--case-registry artifacts/pre-market-daily-monitor/pre-market-cases.json" in text
    assert "--operator-actions artifacts/pre-market-daily-monitor/operator-action-queue.json" in text
    assert "data/pre_market_outreach_review_queue.json" in text
    assert "data/pre_market_outreach_drafts.md" in text


def test_daily_workflow_preserves_human_only_contact_boundary() -> None:
    text = WORKFLOW.read_text(encoding="utf-8").casefold()

    assert "build human-review estate-manager outreach packets" in text
    assert "gmail" not in text
    assert "smtp" not in text
    assert "send-email" not in text
    assert "mailgun" not in text
    assert "sendgrid" not in text
