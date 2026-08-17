"""Conservative canonical decision policy consuming financial Value and risk facts."""

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
class OpportunityDecisionContext:
    """Verified non-financial facts that are allowed to constrain final Decision.

    These inputs are facts produced upstream. They do not calculate Value. Decision
    owns only the classification effect of these facts.
    """

    market_verification_status: str | None = None
    market_is_verified: bool | None = None
    seller_risk: str | None = None
    seller_confidence: str | None = None


@dataclass(frozen=True)
class OpportunityProfitDecision:
    """Canonical commercial decision carrying Value fields through unchanged."""

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
    constraints: tuple[str, ...] = ()


class OpportunityProfitDecisionEngine:
    """Issue the one canonical BUY/WATCH/REJECT decision without recomputing Value."""

    def __init__(self, policy: OpportunityDecisionPolicy | None = None) -> None:
        self.policy = policy or OpportunityDecisionPolicy()

    def decide(
        self,
        value: OpportunityValueReport,
        *,
        context: OpportunityDecisionContext | None = None,
    ) -> OpportunityProfitDecision:
        if not isinstance(value, OpportunityValueReport):
            raise TypeError("decision engine requires canonical OpportunityValueReport")
        if context is not None and not isinstance(context, OpportunityDecisionContext):
            raise TypeError("context must be OpportunityDecisionContext")

        context = context or OpportunityDecisionContext()
        reasons: list[str] = []
        warnings = list(value.warnings)
        constraints: list[str] = []
        profit = value.expected_profit_nok
        roi = value.roi
        confidence = value.confidence

        seller_high_risk = str(context.seller_risk or "").casefold() == "high"
        market_overpriced = (
            str(context.market_verification_status or "").casefold() == "overpriced"
        )
        market_unverified = context.market_is_verified is False

        if seller_high_risk:
            constraints.append("seller_risk_high")
            warnings.append("Seller risk is high; canonical decision rejects the opportunity.")
        if market_overpriced:
            constraints.append("market_overpriced")
            warnings.append("Verified market evidence indicates the opportunity is overpriced.")
        if market_unverified:
            constraints.append("market_verification_required")

        if seller_high_risk or market_overpriced:
            decision = "reject"
            label = "🔴 ارفض"
            if seller_high_risk:
                reasons.append("مخاطر البائع المرتفعة تمنع قرار شراء محافظ.")
            if market_overpriced:
                reasons.append("السعر أعلى من القيمة السوقية المحافظة المتحققة.")
            actionable = True
        elif value.blockers:
            decision = "monitor"
            label = "🟡 راقب"
            reasons.append("البيانات المالية غير مكتملة، لذلك لا يمكن إصدار قرار شراء آمن.")
            actionable = False
        elif market_unverified:
            decision = "monitor"
            label = "🟡 راقب"
            reasons.append("التحقق السوقي غير مكتمل، لذلك لا يمكن تثبيت قرار شراء.")
            actionable = False
            confidence = "insufficient"
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
            confidence=confidence,
            blockers=value.blockers,
            warnings=tuple(dict.fromkeys(warnings)),
            reasons=tuple(reasons),
            is_actionable=actionable,
            constraints=tuple(dict.fromkeys(constraints)),
        )
