from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pytest

from opportunity_engine import Opportunity, evaluate_opportunity


def test_strong_opportunity() -> None:
    item = Opportunity(
        title="اختبار فرصة قوية",
        purchase_price=10000,
        buyer_fee=1000,
        transport_cost=1000,
        repair_cost=0,
        expected_resale_value=20000,
        risk_score=2,
    )

    result = evaluate_opportunity(item)

    assert result.total_cost == 12000
    assert result.expected_profit == 8000
    assert result.return_percent == pytest.approx(66.67, abs=0.01)
    assert result.classification == "🟢 فرصة قوية"


def test_bad_opportunity() -> None:
    item = Opportunity(
        title="اختبار فرصة ضعيفة",
        purchase_price=10000,
        buyer_fee=1000,
        transport_cost=1000,
        repair_cost=1000,
        expected_resale_value=12000,
        risk_score=4,
    )

    result = evaluate_opportunity(item)

    assert result.expected_profit == -1000
    assert result.classification == "🔴 لا تستحق"


def test_invalid_risk_score() -> None:
    item = Opportunity(
        title="مخاطرة غير صحيحة",
        purchase_price=1000,
        expected_resale_value=2000,
        risk_score=6,
    )

    with pytest.raises(ValueError):
        evaluate_opportunity(item)
