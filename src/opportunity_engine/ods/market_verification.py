"""Auditable verification of an opportunity's asking price against verified comparables."""

from __future__ import annotations

from dataclasses import dataclass

from .market_pricing import MarketPriceReport
from .unified_opportunity import UnifiedOpportunity


@dataclass(frozen=True)
class MarketPriceVerification:
    opportunity_id: str
    status: str
    status_label: str
    asking_price_nok: float | None
    conservative_market_value_nok: float | None
    median_market_value_nok: float | None
    discount_vs_conservative: float | None
    discount_vs_median: float | None
    confidence: str
    comparable_count: int
    is_verified: bool
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]


class MarketPriceVerificationEngine:
    """Classify price position without inventing market values or missing prices."""

    def verify(
        self,
        opportunity: UnifiedOpportunity,
        market: MarketPriceReport,
    ) -> MarketPriceVerification:
        asking = opportunity.current_price_nok
        conservative = market.conservative_resale_nok
        median = market.median_price_nok
        reasons: list[str] = []
        warnings = list(market.warnings)

        discount_conservative = _discount(asking, conservative)
        discount_median = _discount(asking, median)
        verified = (
            asking is not None
            and conservative is not None
            and market.comparable_count >= 3
            and market.confidence in {"medium", "high"}
        )

        if asking is None:
            status = "unavailable"
            label = "⚪ السعر المطلوب غير متوفر"
            reasons.append("لا يوجد سعر حالي يمكن مقارنته بالسوق.")
        elif conservative is None:
            status = "unavailable"
            label = "⚪ سوق غير متحقق"
            reasons.append("لا توجد مقارنات سوق موثقة كافية لتحديد القيمة المحافظة.")
        elif not verified:
            status = "needs_review"
            label = "🟡 يحتاج تحققًا يدويًا"
            reasons.append("المقارنة أولية لأن عدد المقارنات أو مستوى الثقة غير كافٍ.")
        elif discount_conservative is not None and discount_conservative >= 0.30:
            status = "strong_discount"
            label = "🟢 خصم سوقي قوي"
            reasons.append("السعر المطلوب أقل من القيمة السوقية المحافظة بما لا يقل عن 30%.")
        elif discount_conservative is not None and discount_conservative >= 0.10:
            status = "moderate_discount"
            label = "🟢 خصم سوقي مقبول"
            reasons.append("السعر المطلوب أقل من القيمة السوقية المحافظة بين 10% و30%.")
        elif discount_conservative is not None and discount_conservative >= -0.05:
            status = "fair_price"
            label = "🟡 قريب من السوق"
            reasons.append("السعر المطلوب قريب من القيمة السوقية المحافظة.")
        else:
            status = "overpriced"
            label = "🔴 أعلى من السوق"
            reasons.append("السعر المطلوب يتجاوز القيمة السوقية المحافظة بأكثر من 5%.")

        if asking is not None and median is not None and asking > median:
            warnings.append("Asking price is above the verified market median.")

        return MarketPriceVerification(
            opportunity_id=opportunity.opportunity_id,
            status=status,
            status_label=label,
            asking_price_nok=_round(asking),
            conservative_market_value_nok=_round(conservative),
            median_market_value_nok=_round(median),
            discount_vs_conservative=_round_ratio(discount_conservative),
            discount_vs_median=_round_ratio(discount_median),
            confidence=market.confidence,
            comparable_count=market.comparable_count,
            is_verified=verified,
            reasons=tuple(reasons),
            warnings=tuple(dict.fromkeys(warnings)),
        )


def _discount(asking: float | None, reference: float | None) -> float | None:
    if asking is None or reference is None or reference <= 0:
        return None
    return (reference - asking) / reference


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def _round_ratio(value: float | None) -> float | None:
    return None if value is None else round(value, 4)
