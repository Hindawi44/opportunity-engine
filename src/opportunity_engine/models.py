from dataclasses import dataclass


@dataclass(frozen=True)
class Opportunity:
    """بيانات فرصة شراء وإعادة بيع."""

    title: str
    purchase_price: float
    buyer_fee: float = 0.0
    transport_cost: float = 0.0
    repair_cost: float = 0.0
    expected_resale_value: float = 0.0
    risk_score: int = 3


@dataclass(frozen=True)
class Evaluation:
    """نتيجة تقييم الفرصة."""

    total_cost: float
    expected_profit: float
    return_percent: float
    maximum_bid: float
    classification: str
    reason: str
