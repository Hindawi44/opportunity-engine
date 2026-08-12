from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"


def test_daily_checkpoint_exposes_optional_google_and_mybring_secrets() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    for line in (
        "GOOGLE_MAPS_API_KEY: ${{ secrets.GOOGLE_MAPS_API_KEY }}",
        "MYBRING_API_UID: ${{ secrets.MYBRING_API_UID }}",
        "MYBRING_API_KEY: ${{ secrets.MYBRING_API_KEY }}",
        "MYBRING_CLIENT_URL: ${{ secrets.MYBRING_CLIENT_URL }}",
        "MYBRING_CUSTOMER_NUMBER: ${{ secrets.MYBRING_CUSTOMER_NUMBER }}",
    ):
        assert line in text

    assert "src/opportunity_engine/logistics/official_route_freight.py" in text
    assert "tests/test_official_route_freight_v1.py" in text
    assert "pytest tests/test_official_route_freight_v1.py -q" in text
    assert "pytest tests/test_official_route_freight_workflow_wiring_v1.py -q" in text


def test_route_and_freight_secrets_do_not_change_read_only_permissions() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "permissions:\n  contents: read\n  actions: read" in text
    assert "automatic_purchase" in text
    assert "automatic_payment" in text
    assert "automatic_contact" in text
    assert "automatic_bid" in text
