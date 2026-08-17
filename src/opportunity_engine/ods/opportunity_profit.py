"""Conservative decision policy consuming canonical financial value."""

from __future__ import annotations

from dataclasses import dataclass

from .opportunity_value import OpportunityValueReport


@dataclass(frozen=True)
class OpportunityDecisionPolicy:
    """Thresholds used only to classify an already-calculated Value report."""

    strong_min_roi: float = 0.35
    monitor_min_roi: float = 0.15
    minimum_profit_nok: float = 2_000.0

    def __post_init__(self) -> None:
        for name, value in (
            ("strong_min_roi", self.strong_min_roi),
            ("monitor_min_roi", self.monitor_min_roi),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be expressed as a decimal between 0 and 1")
        if self.monitor_min_roi > self.strong_min_roi:
            raise ValueError("monitor_min_roi must not exceed strong_min_roi")
        if self.minimum_profit_nok < 0:
            raise ValueError("minimum_profit_nok must not be negative")


@dataclass(frozen=True)
class OpportunityProfitDecision:
    """Auditable decision carrying through canonical Value fields unchanged."""

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
    """Classify canonical Value as buy, monitor, or reject without recomputing it."""

    def __init__(self, policy: OpportunityDecisionPolicy | None = None) -> None:
        self.policy = policy or OpportunityDecisionPolicy()

    def decide(self, value: OpportunityValueReport) -> OpportunityProfitDecision:
        if not isinstance(value, OpportunityValueReport):
            raise TypeError("decision engine requires canonical OpportunityValueReport")

        reasons: list[str] = []
        profit = value.expected_profit_nok
        roi = value.roi

        if value.blockers:
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
            and value.confidence in {"medium", "high"}
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

        return OpportunityProfitDecision(
            opportunity_id=value.opportunity_id,
            decision=decision,
            decision_label=label,
            conservative_resale_nok=value.conservative_resale_nok,
            total_cost_nok=value.total_cost_nok,
            expected_profit_nok=value.expected_profit_nok,
            roi=value.roi,
            margin_on_resale=value.margin_on_resale,
            maximum_total_cost_nok=value.maximum_total_cost_nok,
            maximum_purchase_price_nok=value.maximum_purchase_price_nok,
            confidence=value.confidence,
            blockers=value.blockers,
            warnings=value.warnings,
            reasons=tuple(reasons),
            is_actionable=actionable,
        )
