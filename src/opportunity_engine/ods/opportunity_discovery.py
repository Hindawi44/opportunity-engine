"""Deterministic discovery ranking for opportunities in the current pipeline run."""

from __future__ import annotations

from dataclasses import dataclass

from .market_verification import MarketPriceVerification
from .opportunity_profit import OpportunityProfitDecision
from .opportunity_scoring import OpportunityScore
from .price_history import PriceHistorySummary
from .seller_reliability import SellerReliabilityReport
from .unified_opportunity import UnifiedOpportunity


@dataclass(frozen=True)
class OpportunityDiscoveryReport:
    opportunity_id: str
    discovery_score: float
    tier: str
    tier_label: str
    is_exceptional: bool
    requires_immediate_review: bool
    suggested_action: str
    signals: tuple[str, ...]
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]


class OpportunityDiscoveryEngine:
    """Highlight exceptional candidates without inventing market or historical facts.

    The score ranks evidence available in the current run. It does not claim that an
    opportunity is the best in Norway or over a historical period unless such cohort
    data is explicitly available elsewhere.
    """

    def discover(
        self,
        opportunity: UnifiedOpportunity,
        decision: OpportunityProfitDecision,
        score: OpportunityScore,
        verification: MarketPriceVerification,
        history: PriceHistorySummary,
        seller: SellerReliabilityReport,
    ) -> OpportunityDiscoveryReport:
        points = 0.0
        signals: list[str] = []
        reasons: list[str] = []
        warnings: list[str] = []

        # The base scoring engine already evaluates observable quality, resale,
        # logistics, confidence and known risk. Discovery adds verified evidence,
        # but must never erase a valid preliminary score merely because economics
        # are still incomplete.
        preliminary_floor = max(0.0, min(score.total_score, 59.0))
        points += min(35.0, score.total_score * 0.35)
        reasons.append(f"درجة جودة الفرصة الأساسية {score.total_score:.0f}/100.")

        discount = verification.discount_vs_conservative
        if verification.is_verified and discount is not None:
            market_points = max(0.0, min(25.0, discount / 0.40 * 25.0))
            points += market_points
            if discount >= 0.30:
                signals.append("verified_strong_market_discount")
                reasons.append("السعر أقل من القيمة السوقية المحافظة بنسبة قوية ومتحققة.")
            elif discount >= 0.10:
                signals.append("verified_market_discount")
                reasons.append("يوجد خصم سوقي متحقق.")
        elif verification.status == "overpriced":
            points -= 25.0
            warnings.append("السعر الحالي أعلى من القيمة السوقية المحافظة.")
        else:
            warnings.append("لا توجد أدلة سوق كافية لاحتساب ميزة سعرية مؤكدة.")

        if decision.expected_profit_nok is not None and decision.roi is not None:
            profit_points = min(10.0, max(0.0, decision.expected_profit_nok / 20_000.0 * 10.0))
            roi_points = min(10.0, max(0.0, decision.roi / 0.60 * 10.0))
            points += profit_points + roi_points
            if decision.roi >= 0.35 and decision.expected_profit_nok >= 2_000:
                signals.append("strong_verified_profitability")
                reasons.append("الربح والعائد المتوقعان يتجاوزان الحدود المحافظة.")
        else:
            warnings.append("الربحية غير مكتملة بسبب غياب سعر سوق أو تكاليف مؤكدة.")

        if history.significant_drop:
            points += 10.0
            signals.append("significant_price_drop")
            reasons.append("السعر انخفض 10% أو أكثر منذ أول رصد.")
        elif history.status == "price_drop":
            points += 5.0
            signals.append("recent_price_drop")
        elif history.status == "price_increase":
            points -= 3.0
            warnings.append("السعر ارتفع منذ الرصد السابق.")

        if seller.score is not None:
            points += min(10.0, max(0.0, seller.score / 100.0 * 10.0))
            if seller.risk == "low":
                signals.append("low_seller_risk")
            elif seller.risk == "high":
                points -= 15.0
                warnings.append("مخاطر البائع مرتفعة وفق بيانات المصدر.")
        else:
            warnings.append("موثوقية البائع غير متحققة.")

        # Missing evidence is a reason to withhold a buy recommendation, not a
        # proven commercial loss. Keep it visible without subtracting the entire
        # preliminary score a second time.
        if decision.blockers:
            warnings.append("توجد فجوات أدلة تمنع إصدار قرار شراء آمن.")

        points = max(points, preliminary_floor)
        if decision.decision == "reject":
            points = min(points, 39.0)
        elif not decision.is_actionable:
            points = min(points, 59.0)

        discovery_score = round(max(0.0, min(points, 100.0)), 2)
        tier, label = self._tier(discovery_score)
        exceptional = (
            discovery_score >= 80
            and decision.decision == "buy"
            and verification.is_verified
            and not decision.blockers
            and seller.risk != "high"
        )
        immediate = exceptional or (
            discovery_score >= 70
            and history.significant_drop
            and opportunity.ends_at is not None
        )

        if exceptional:
            action = "راجع وحد المزايدة الآن قبل أي التزام مالي."
        elif discovery_score >= 60:
            action = "تحقق من التكاليف والمقارنات الناقصة ثم راقب الفرصة."
        else:
            action = "لا تعطِ الفرصة أولوية حاليًا."

        return OpportunityDiscoveryReport(
            opportunity_id=opportunity.opportunity_id,
            discovery_score=discovery_score,
            tier=tier,
            tier_label=label,
            is_exceptional=exceptional,
            requires_immediate_review=immediate,
            suggested_action=action,
            signals=tuple(dict.fromkeys(signals)),
            reasons=tuple(dict.fromkeys(reasons)),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    @staticmethod
    def _tier(score: float) -> tuple[str, str]:
        if score >= 80:
            return "exceptional", "🟢 فرصة استثنائية"
        if score >= 65:
            return "strong", "🟢 فرصة قوية"
        if score >= 50:
            return "watch", "🟡 تستحق المراقبة"
        return "low", "⚪ أولوية منخفضة"
