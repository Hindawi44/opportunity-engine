from .models import Evaluation, Opportunity


def evaluate_opportunity(
    opportunity: Opportunity,
    target_margin: float = 0.30,
) -> Evaluation:
    """احسب تكلفة المزاد والربح وصنّف الفرصة بطريقة متحفظة."""

    numeric_costs = [
        opportunity.purchase_price,
        opportunity.buyer_fee,
        opportunity.transport_cost,
        opportunity.repair_cost,
        opportunity.dismantling_cost,
        opportunity.storage_cost,
        opportunity.other_costs,
        opportunity.expected_resale_value,
    ]
    if any(value < 0 for value in numeric_costs):
        raise ValueError("costs and values cannot be negative")
    if not 1 <= opportunity.risk_score <= 5:
        raise ValueError("risk_score must be between 1 and 5")
    if not 0 <= opportunity.vat_rate <= 1:
        raise ValueError("vat_rate must be between 0 and 1")
    if not 0 < target_margin < 1:
        raise ValueError("target_margin must be between 0 and 1")

    vat_cost = (
        opportunity.purchase_price * opportunity.vat_rate
        if opportunity.vat_applies_to_bid
        else 0.0
    )
    extra_costs = (
        opportunity.buyer_fee
        + opportunity.transport_cost
        + opportunity.repair_cost
        + opportunity.dismantling_cost
        + opportunity.storage_cost
        + opportunity.other_costs
        + vat_cost
    )
    total_cost = opportunity.purchase_price + extra_costs
    expected_profit = opportunity.expected_resale_value - total_cost
    return_percent = (expected_profit / total_cost * 100) if total_cost else 0.0

    # الحد الأقصى للمزايدة، مع احتساب أن ضريبة القيمة المضافة ترتفع مع سعر المزايدة.
    maximum_total_cost = opportunity.expected_resale_value * (1 - target_margin)
    fixed_extra_costs = extra_costs - vat_cost
    bid_multiplier = 1 + opportunity.vat_rate if opportunity.vat_applies_to_bid else 1
    maximum_bid = max(0.0, (maximum_total_cost - fixed_extra_costs) / bid_multiplier)

    if expected_profit <= 0 or opportunity.risk_score >= 5:
        classification = "🔴 لا تستحق"
        reason = "الربح المتوقع غير موجب أو مستوى المخاطرة مرتفع جدًا."
    elif return_percent >= 35 and opportunity.risk_score <= 2:
        classification = "🟢 فرصة قوية"
        reason = "عائد جيد مع مستوى مخاطرة منخفض وبعد احتساب جميع التكاليف."
    else:
        classification = "🟡 تحتاج مراقبة"
        reason = "قد تكون مربحة، لكن السعر أو التكاليف أو المخاطرة تحتاج متابعة."

    return Evaluation(
        vat_cost=round(vat_cost, 2),
        extra_costs=round(extra_costs, 2),
        total_cost=round(total_cost, 2),
        expected_profit=round(expected_profit, 2),
        return_percent=round(return_percent, 2),
        maximum_bid=round(maximum_bid, 2),
        classification=classification,
        reason=reason,
    )
