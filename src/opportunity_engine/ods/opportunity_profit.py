"""Conservative profit and purchase decision for auction opportunities."""

from __future__ import annotations

from dataclasses import dataclass

from .market_pricing import MarketPriceReport
from .real_cost import RealCostReport


@dataclass(frozen=True)
class OpportunityDecisionPolicy:
    """Explicit thresholds used by the decision engine."""

    strong_min_roi: float = 0.35
    monitor_min_roi: float = 0.15
    minimum_profit_nok: float = 2_000.0
    target_roi_for_max_bid: float = 0.35

    def __post_init__(self) -> None:
        for name, value in (
            ("strong_min_roi", self.strong_min_roi),
            ("monitor_min_roi", self.monitor_min_roi),
            ("target_roi_for_max_bid", self.target_roi_for_max_bid),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be expressed as a decimal between 0 and 1")
        if self.monitor_min_roi > self.strong_min_roi:
            raise ValueError("monitor_min_roi must not exceed strong_min_roi")
        if self.minimum_profit_nok < 0:
            raise ValueError("minimum_profit_nok must not be negative")


@dataclass(frozen=True)
class OpportunityProfitDecision:
    """Auditable result combining market value and real acquisition cost."""

    opportunity_id: str
    decision: str
    decision_label: str
    conservative_resale_nok: float | None
    total_cost_nok: float | None
    expected_profit_nok: float | None
    roi: float | None
    margin_on_resale: float | None
    maximum_total_cost_nok: float | None
    maximum_purchase_price_nok: float | None
    confidence: str
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    reasons: tuple[str, ...]
    is_actionable: bool


class OpportunityProfitDecisionEngine:
    """Issue a conservative buy, monitor, or reject decision."""

    def __init__(self, policy: OpportunityDecisionPolicy | None = None) -> None:
        self.policy = policy or OpportunityDecisionPolicy()

    def decide(
        self,
        market: MarketPriceReport,
        costs: RealCostReport,
    ) -> OpportunityProfitDecision:
        blockers: list[str] = []
        warnings = list(market.warnings) + list(costs.warnings)
        reasons: list[str] = []

        resale = market.conservative_resale_nok
        total = costs.total_cost_nok

        if resale is None:
            blockers.append("conservative_resale_nok")
        if total is None:
            blockers.append("total_cost_nok")
        if market.confidence == "insufficient":
            blockers.append("market_comparables")
        if not costs.is_complete:
            blockers.extend(f"cost:{name}" for name in costs.missing_fields)

        profit = None if resale is None or total is None else resale - total
        roi = None if profit is None or total is None or total <= 0 else profit / total
        margin = None if profit is None or resale is None or resale <= 0 else profit / resale

        maximum_total = None
        maximum_purchase = None
        if resale is not None:
            maximum_total = resale / (1 + self.policy.target_roi_for_max_bid)
            if costs.purchase_price_nok is not None and total is not None:
                non_purchase_costs = total - costs.purchase_price_nok
                maximum_purchase = max(0.0, maximum_total - non_purchase_costs)

        if blockers:
            decision = "monitor"
            label = "🟡 راقب"
            reasons.append("البيانات غير مكتملة، لذلك لا يمكن إصدار قرار شراء آمن.")
            actionable = False
        elif profit is not None and profit <= 0:
            decision = "reject"
            label = "🔴 ارفض"
            reasons.append("قيمة إعادة البيع المحافظة لا تغطي التكلفة النهائية.")
            actionable = True
        elif roi is not None and profit is not None and (
            roi >= self.policy.strong_min_roi
            and profit >= self.policy.minimum_profit_nok
            and market.confidence in {"medium", "high"}
        ):
            decision = "buy"
            label = "🟢 اشترِ"
            reasons.append("الربح والعائد يتجاوزان الحد المحافظ المطلوب.")
            actionable = True
        elif roi is not None and roi >= self.policy.monitor_min_roi:
            decision = "monitor"
            label = "🟡 راقب"
            reasons.append("الفرصة موجبة، لكن هامش الأمان أو الثقة لا يكفيان للشراء المباشر.")
            actionable = True
        else:
            decision = "reject"
            label = "🔴 ارفض"
            reasons.append("العائد المتوقع أقل من الحد الأدنى المقبول.")
            actionable = True

        if market.confidence == "low":
            warnings.append("Market confidence is low; verify comparables manually.")
        if maximum_purchase is not None and costs.purchase_price_nok is not None:
            if costs.purchase_price_nok > maximum_purchase:
                warnings.append("Current purchase price exceeds the conservative maximum bid.")

        confidence = self._combined_confidence(market, costs, blockers)
        return OpportunityProfitDecision(
            opportunity_id=market.opportunity_id,
            decision=decision,
            decision_label=label,
            conservative_resale_nok=_round(resale),
            total_cost_nok=_round(total),
            expected_profit_nok=_round(profit),
            roi=_round_ratio(roi),
            margin_on_resale=_round_ratio(margin),
            maximum_total_cost_nok=_round(maximum_total),
            maximum_purchase_price_nok=_round(maximum_purchase),
            confidence=confidence,
            blockers=tuple(dict.fromkeys(blockers)),
            warnings=tuple(dict.fromkeys(warnings)),
            reasons=tuple(reasons),
            is_actionable=actionable,
        )

    @staticmethod
    def _combined_confidence(
        market: MarketPriceReport,
        costs: RealCostReport,
        blockers: list[str],
    ) -> str:
        if blockers:
            return "insufficient"
        if not costs.is_complete or market.confidence == "low":
            return "low"
        return market.confidence


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def _round_ratio(value: float | None) -> float | None:
    return None if value is None else round(value, 4)
