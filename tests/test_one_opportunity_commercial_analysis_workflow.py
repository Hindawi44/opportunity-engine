from pathlib import Path


WORKFLOW = Path(".github/workflows/one-opportunity-commercial-analysis.yaml")


def test_workflow_exposes_bounded_manual_commercial_inputs() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    for token in (
        "opportunity_identity:",
        "quantity_condition_status:",
        "final_payable_price_nok:",
        "transport_nok:",
        "conservative_resale_nok:",
        "resale_comparable_count:",
        "commercial_review_note:",
    ):
        assert token in text
    assert "manual-read-only-commercial-analysis" in text
    assert "automatic_purchase" in text
    assert "actions: read" in text
    assert "one-opportunity-commercial-analysis" in text


def test_workflow_uses_environment_variables_for_user_inputs() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert '--opportunity-id "$COMMERCIAL_OPPORTUNITY_ID"' in text
    assert '--review-note "$COMMERCIAL_REVIEW_NOTE"' in text
    assert 'expected = os.environ["EXPECTED_OPPORTUNITY_ID"].strip()' in text
