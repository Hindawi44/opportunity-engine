from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pytest

from opportunity_engine import Opportunity, evaluate_opportunity


def test_vat_and_full_auction_costs() -> None:
    item = Opportunity(
        title="مزاد مع ضريبة وتكاليف كاملة",
        purchase_price=10000,
        buyer_fee=1000,
        transport_cost=1500,
        dismantling_cost=500,
        storage_cost=250,
        repair_cost=750,
        other_costs=500,
        expected_resale_value=25000,
        risk_score=2,
        vat_rate=0.25,
        vat_applies_to_bid=True,
    )

    result = evaluate_opportunity(item)

    assert result.vat_cost == 2500
    assert result.extra_costs == 7000
    assert result.total_cost == 17000
    assert result.expected_profit == 8000
    assert result.return_percent == pytest.approx(47.06, abs=0.01)
    assert result.maximum_bid == pytest.approx(10400, abs=0.01)
    assert result.classification == "🟢 فرصة قوية"


def test_vat_not_applied_to_bid() -> None:
    item = Opportunity(
        title="مزاد بلا ضريبة على المزايدة",
        purchase_price=10000,
        expected_resale_value=15000,
        risk_score=3,
        vat_rate=0.25,
        vat_applies_to_bid=False,
    )

    result = evaluate_opportunity(item)

    assert result.vat_cost == 0
    assert result.total_cost == 10000
    assert result.maximum_bid == 10500
