"""Explain opportunity decisions from auditable engine outputs only."""

from __future__ import annotations

from dataclasses import dataclass

from .market_verification import MarketPriceVerification
from .opportunity_profit import OpportunityProfitDecision
from .opportunity_scoring import OpportunityScore
from .price_history import PriceHistorySummary
from .seller_reliability import SellerReliabilityReport
from .unified_opportunity import UnifiedOpportunity


@dataclass(frozen=True)
class OpportunityIntelligenceReport:
    opportunity_id: str
    recommendation: str
    recommendation_label: str
    headline: str
    summary: str
    strengths: tuple[str, ...]
    risks: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    next_actions: tuple[str, ...]
    confidence: str
    is_actionable: bool


class OpportunityIntelligenceEngine:
    """Create a deterministic explanation without inventing facts or using an LLM."""

    def explain(
        self,
        opportunity: UnifiedOpportunity,
        decision: OpportunityProfitDecision,
        score: OpportunityScore,
        verification: MarketPriceVerification,
        history: PriceHistorySummary,
        seller: SellerReliabilityReport,
    ) -> OpportunityIntelligenceReport:
        strengths: list[str] = []
        risks: list[str] = []
        missing: list[str] = []
        actions: list[str] = []

        if decision.expected_profit_nok is not None and decision.expected_profit_nok > 0:
            strengths.append(f"الربح المحافظ المتوقع {decision.expected_profit_nok:,.0f} NOK.")
        if decision.roi is not None and decision.roi >= 0.35:
            strengths.append(f"العائد المتوقع قوي عند {decision.roi * 100:.1f}%.")
        if verification.status == "strong_discount":
            strengths.append("السعر الحالي أقل من القيمة السوقية المحافظة بفارق قوي.")
        elif verification.status == "moderate_discount":
            strengths.append("السعر الحالي يتضمن خصمًا سوقيًا مقبولًا.")
        elif verification.status == "overpriced":
            risks.append("السعر المطلوب أعلى من القيمة السوقية المحافظة.")
        elif not verification.is_verified:
            missing.append("تحقق سوقي موثوق بثلاث مقارنات مناسبة على الأقل.")

        if history.significant_drop:
            strengths.append("السعر انخفض 10% أو أكثر منذ أول رصد.")
        elif history.status == "price_increase":
            risks.append("السعر ارتفع منذ الرصد السابق.")
        if history.age_days >= 30:
            risks.append(f"الإعلان قديم نسبيًا؛ عمره {history.age_days} يومًا.")

        if seller.risk == "low":
            strengths.append("مؤشرات البائع المتاحة تشير إلى مخاطر منخفضة.")
        elif seller.risk == "high":
            risks.append("بيانات البائع المتاحة تشير إلى مخاطر مرتفعة.")
        elif seller.confidence == "insufficient":
            missing.append("بيانات موثقة كافية عن البائع.")

        if score.resale_score >= 12:
            strengths.append("الأصل يبدو سهل إعادة البيع نسبيًا وفق وصف الإعلان.")
        elif score.resale_score <= 5:
            risks.append("إعادة البيع قد تكون صعبة وفق وصف الإعلان.")
        if score.logistics_score <= 5:
            risks.append("النقل أو التفكيك قد يكون معقدًا أو مكلفًا.")

        for blocker in decision.blockers:
            missing.append(_human_blocker(blocker))
        risks.extend(decision.warnings)

        if decision.maximum_purchase_price_nok is not None:
            actions.append(
                f"عدم تجاوز سعر شراء محافظ قدره {decision.maximum_purchase_price_nok:,.0f} NOK."
            )
        if not verification.is_verified:
            actions.append("جمع مقارنات سوق موثقة قبل أي شراء.")
        if seller.confidence in {"insufficient", "low"}:
            actions.append("التحقق من هوية البائع وشروط التسليم قبل الدفع.")
        if history.significant_drop:
            actions.append("فحص سبب التخفيض والتأكد من عدم وجود عيب أو نقص جديد.")
        if not actions:
            actions.append("مراجعة الإعلان والصور وشروط الاستلام يدويًا قبل القرار النهائي.")

        strengths = _unique(strengths)
        risks = _unique(risks)
        missing = _unique(missing)
        actions = _unique(actions)
        recommendation, label = _recommendation(decision, verification, seller)
        confidence = _confidence(decision, verification, seller, missing)
        headline = _headline(recommendation, score.total_score)
        summary = _summary(recommendation, strengths, risks, missing)

        return OpportunityIntelligenceReport(
            opportunity_id=opportunity.opportunity_id,
            recommendation=recommendation,
            recommendation_label=label,
            headline=headline,
            summary=summary,
            strengths=tuple(strengths),
            risks=tuple(risks),
            missing_evidence=tuple(missing),
            next_actions=tuple(actions),
            confidence=confidence,
            is_actionable=decision.is_actionable and not missing,
        )


def _recommendation(
    decision: OpportunityProfitDecision,
    verification: MarketPriceVerification,
    seller: SellerReliabilityReport,
) -> tuple[str, str]:
    if decision.decision == "reject" or verification.status == "overpriced" or seller.risk == "high":
        return "reject", "🔴 ارفض"
    if decision.decision == "buy" and verification.is_verified and seller.risk != "high":
        return "buy", "🟢 اشترِ"
    return "monitor", "🟡 راقب"


def _confidence(
    decision: OpportunityProfitDecision,
    verification: MarketPriceVerification,
    seller: SellerReliabilityReport,
    missing: list[str],
) -> str:
    if missing or decision.confidence == "insufficient":
        return "insufficient"
    if decision.confidence == "high" and verification.is_verified and seller.confidence in {"medium", "high"}:
        return "high"
    if decision.confidence in {"medium", "high"} and verification.is_verified:
        return "medium"
    return "low"


def _headline(recommendation: str, score: float) -> str:
    labels = {
        "buy": "فرصة قوية قابلة للدراسة للشراء",
        "monitor": "فرصة تحتاج استكمال تحقق قبل الشراء",
        "reject": "الفرصة لا تحقق شروط الشراء المحافظ",
    }
    return f"{labels[recommendation]} — الدرجة {score:.0f}/100"


def _summary(recommendation: str, strengths: list[str], risks: list[str], missing: list[str]) -> str:
    if recommendation == "buy":
        opening = "المؤشرات المالية والسوقية تدعم دراسة الشراء ضمن الحد الأقصى المحدد."
    elif recommendation == "reject":
        opening = "المخاطر أو السعر أو العائد لا يحقق شروط الشراء المحافظ."
    else:
        opening = "لا توجد أدلة كافية لإصدار قرار شراء آمن حتى الآن."
    parts = [opening]
    if strengths:
        parts.append(f"أهم نقطة قوة: {strengths[0]}")
    if risks:
        parts.append(f"أهم مخاطرة: {risks[0]}")
    if missing:
        parts.append(f"أهم معلومة ناقصة: {missing[0]}")
    return " ".join(parts)


def _human_blocker(blocker: str) -> str:
    mapping = {
        "conservative_resale_nok": "قيمة إعادة بيع محافظة.",
        "total_cost_nok": "التكلفة النهائية الكاملة.",
        "market_comparables": "مقارنات سوق موثقة.",
    }
    if blocker.startswith("cost:"):
        return f"تكلفة مؤكدة للبند {blocker.split(':', 1)[1]}."
    return mapping.get(blocker, blocker)


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))
