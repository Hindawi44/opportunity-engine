from dataclasses import dataclass


@dataclass(frozen=True)
class Opportunity:
    """بيانات فرصة شراء وإعادة بيع، بما فيها تكاليف المزاد."""

    title: str
    purchase_price: float
    buyer_fee: float = 0.0
    transport_cost: float = 0.0
    repair_cost: float = 0.0
    dismantling_cost: float = 0.0
    storage_cost: float = 0.0
    other_costs: float = 0.0
    expected_resale_value: float = 0.0
    risk_score: int = 3
    auction_url: str = ""
    vat_rate: float = 0.25
    vat_applies_to_bid: bool = False


@dataclass(frozen=True)
class Evaluation:
    """نتيجة تقييم الفرصة."""

    vat_cost: float
    extra_costs: float
    total_cost: float
    expected_profit: float
    return_percent: float
    maximum_bid: float
    classification: str
    reason: str
