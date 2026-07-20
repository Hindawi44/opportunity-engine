"""Transparent 0-100 scoring for resale and liquidation opportunities."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .opportunity_profit import OpportunityProfitDecision
from .unified_opportunity import UnifiedOpportunity


@dataclass(frozen=True)
class OpportunityScore:
    opportunity_id: str
    total_score: float
    financial_score: float
    confidence_score: float
    data_quality_score: float
    resale_score: float
    logistics_score: float
    risk_penalty: float
    grade: str
    reasons: tuple[str, ...]


class OpportunityScoringEngine:
    """Score opportunities conservatively without inventing missing facts."""

    def score(
        self,
        opportunity: UnifiedOpportunity,
        decision: OpportunityProfitDecision,
    ) -> OpportunityScore:
        financial = self._financial(decision)
        confidence = {
            "high": 15.0,
            "medium": 11.0,
            "low": 5.0,
            "insufficient": 0.0,
        }.get(decision.confidence, 0.0)
        data_quality = max(0.0, 15.0 - min(len(opportunity.missing_fields), 6) * 2.5)
        resale = self._resale(opportunity)
        logistics = self._logistics(opportunity)
        risk_penalty = min(25.0, len(decision.blockers) * 4.0 + len(decision.warnings) * 1.5)

        raw = financial + confidence + data_quality + resale + logistics - risk_penalty
        if decision.decision == "reject":
            raw = min(raw, 39.0)
        elif decision.decision == "monitor" and not decision.is_actionable:
            raw = min(raw, 59.0)
        total = round(max(0.0, min(raw, 100.0)), 2)

        reasons = (
            f"financial={financial:.1f}/40",
            f"confidence={confidence:.1f}/15",
            f"data_quality={data_quality:.1f}/15",
            f"resale={resale:.1f}/15",
            f"logistics={logistics:.1f}/15",
            f"risk_penalty={risk_penalty:.1f}",
        )
        return OpportunityScore(
            opportunity_id=opportunity.opportunity_id,
            total_score=total,
            financial_score=round(financial, 2),
            confidence_score=round(confidence, 2),
            data_quality_score=round(data_quality, 2),
            resale_score=round(resale, 2),
            logistics_score=round(logistics, 2),
            risk_penalty=round(risk_penalty, 2),
            grade=self._grade(total),
            reasons=reasons,
        )

    @staticmethod
    def _financial(decision: OpportunityProfitDecision) -> float:
        if decision.expected_profit_nok is None or decision.roi is None:
            return 0.0
        roi_score = max(0.0, min(decision.roi / 0.60, 1.0)) * 24.0
        profit_score = max(0.0, min(decision.expected_profit_nok / 20_000.0, 1.0)) * 16.0
        return roi_score + profit_score

    @staticmethod
    def _resale(opportunity: UnifiedOpportunity) -> float:
        text = f"{opportunity.title} {opportunity.description}".casefold()
        easy = (
            "kontorstol", "kontormøbel", "butikkinnredning", "hylle", "verktøy",
            "symaskin", "møbel", "lampe", "skjerm", "bord", "stol",
        )
        difficult = (
            "spesialbygget", "komplett fabrikk", "produksjonslinje", "defekt",
            "ukjent stand", "reservedeler", "tungmaskin",
        )
        score = 8.0
        if any(word in text for word in easy):
            score += 5.0
        if any(word in text for word in difficult):
            score -= 6.0
        if opportunity.current_price_nok is not None:
            score += 2.0
        return max(0.0, min(score, 15.0))

    @staticmethod
    def _logistics(opportunity: UnifiedOpportunity) -> float:
        text = re.sub(r"\s+", " ", f"{opportunity.title} {opportunity.description}".casefold())
        score = 10.0
        hard = (
            "demontering", "må demonteres", "truck nødvendig", "kran nødvendig",
            "hentes med lastebil", "produksjonslinje", "tung",
        )
        easy = ("kan sendes", "pakkes", "pall", "lett", "demontert")
        if any(word in text for word in hard):
            score -= 7.0
        if any(word in text for word in easy):
            score += 3.0
        if opportunity.city:
            score += 2.0
        return max(0.0, min(score, 15.0))

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 80:
            return "A"
        if score >= 65:
            return "B"
        if score >= 50:
            return "C"
        if score >= 35:
            return "D"
        return "E"
