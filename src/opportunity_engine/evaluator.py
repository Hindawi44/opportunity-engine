from .models import Evaluation, Opportunity


def evaluate_opportunity(
    opportunity: Opportunity,
    target_margin: float = 0.30,
) -> Evaluation:
    """احسب التكلفة والربح وصنّف الفرصة بطريقة متحفظة."""

    if opportunity.purchase_price < 0:
        raise ValueError("purchase_price cannot be negative")
    if opportunity.expected_resale_value < 0:
        raise ValueError("expected_resale_value cannot be negative")
    if not 1 <= opportunity.risk_score <= 5:
        raise ValueError("risk_score must be between 1 and 5")
    if not 0 < target_margin < 1:
        raise ValueError("target_margin must be between 0 and 1")

    extra_costs = (
        opportunity.buyer_fee
        + opportunity.transport_cost
        + opportunity.repair_cost
    )
    total_cost = opportunity.purchase_price + extra_costs
    expected_profit = opportunity.expected_resale_value - total_cost
    return_percent = (expected_profit / total_cost * 100) if total_cost else 0.0

    # الحد الأقصى للشراء مع هامش أمان وربح مستهدف.
    maximum_total_cost = opportunity.expected_resale_value * (1 - target_margin)
    maximum_bid = max(0.0, maximum_total_cost - extra_costs)

    if expected_profit <= 0 or opportunity.risk_score >= 5:
        classification = "🔴 لا تستحق"
        reason = "الربح المتوقع غير موجب أو مستوى المخاطرة مرتفع جدًا."
    elif return_percent >= 35 and opportunity.risk_score <= 2:
        classification = "🟢 فرصة قوية"
        reason = "عائد جيد مع مستوى مخاطرة منخفض."
    else:
        classification = "🟡 تحتاج مراقبة"
        reason = "قد تكون مربحة، لكن السعر أو المخاطرة يحتاجان متابعة."

    return Evaluation(
        total_cost=round(total_cost, 2),
        expected_profit=round(expected_profit, 2),
        return_percent=round(return_percent, 2),
        maximum_bid=round(maximum_bid, 2),
        classification=classification,
        reason=reason,
    )
