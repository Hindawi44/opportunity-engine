from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"
ARCHIVED = ROOT / "docs/archive/legacy-six-market-checkpoint-20260919.yaml.txt"


def test_logistics_secret_wiring_is_historical_not_in_event_pilot() -> None:
    old = ARCHIVED.read_text(encoding="utf-8")
    active = ACTIVE.read_text(encoding="utf-8")
    for line in (
        "GOOGLE_MAPS_API_KEY: ${{ secrets.GOOGLE_MAPS_API_KEY }}",
        "MYBRING_API_UID: ${{ secrets.MYBRING_API_UID }}",
        "MYBRING_API_KEY: ${{ secrets.MYBRING_API_KEY }}",
        "MYBRING_CLIENT_URL: ${{ secrets.MYBRING_CLIENT_URL }}",
        "MYBRING_CUSTOMER_NUMBER: ${{ secrets.MYBRING_CUSTOMER_NUMBER }}",
    ):
        assert line in old
        assert line not in active
    assert "src/opportunity_engine/logistics/official_route_freight.py" in old
    assert "pytest tests/test_official_route_freight_v1.py -q" in old


def test_norway_pilot_stays_read_only_without_route_or_freight_actions() -> None:
    old = ARCHIVED.read_text(encoding="utf-8")
    active = ACTIVE.read_text(encoding="utf-8")
    assert "permissions:\n  contents: read\n  actions: read" in old
    for name in ("automatic_purchase", "automatic_payment", "automatic_contact", "automatic_bid"):
        assert name in old
        assert name not in active
    assert "permissions:\n  contents: read" in active
    assert "contents: write" not in active
    assert "run_event_first_hunter_pilot.py" in active
