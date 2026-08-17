from opportunity_engine.ods.market_verification import MarketPriceVerification
from opportunity_engine.ods.opportunity_intelligence import OpportunityIntelligenceEngine
from opportunity_engine.ods.opportunity_profit import (
    OpportunityDecisionContext,
    OpportunityProfitDecisionEngine,
)
from opportunity_engine.ods.opportunity_scoring import OpportunityScore
from opportunity_engine.ods.opportunity_value import OpportunityValueReport
from opportunity_engine.ods.price_history import PriceHistorySummary
from opportunity_engine.ods.seller_reliability import SellerReliabilityReport
from opportunity_engine.ods.unified_opportunity import UnifiedOpportunity


def _value() -> OpportunityValueReport:
    return OpportunityValueReport(
        opportunity_id="decision-owner-1",
        conservative_resale_nok=25_000,
        total_cost_nok=13_000,
        expected_profit_nok=12_000,
        roi=0.9231,
        margin_on_resale=0.48,
        maximum_total_cost_nok=18_518.52,
        maximum_purchase_price_nok=15_518.52,
        confidence="high",
        blockers=(),
        warnings=(),
    )


def _opportunity() -> UnifiedOpportunity:
    return UnifiedOpportunity(
        opportunity_id="decision-owner-1",
        source_name="Auksjonen.no",
        source_document_id="1",
        title="Butikkinnredning",
        url="https://example.test/1",
        description="Demontert butikkinnredning på pall",
        current_price_nok=10_000,
        city="Trondheim",
        ends_at=None,
        fee_text="10%",
        mva_status="included",
        image_urls=(),
        missing_fields=(),
        raw_metadata={},
    )


def _score() -> OpportunityScore:
    return OpportunityScore(
        opportunity_id="decision-owner-1",
        total_score=88,
        financial_score=38,
        confidence_score=15,
        data_quality_score=15,
        resale_score=13,
        logistics_score=12,
        risk_penalty=5,
        grade="A",
        reasons=(),
    )


def _verification(status: str = "strong_discount", verified: bool = True) -> MarketPriceVerification:
    return MarketPriceVerification(
        opportunity_id="decision-owner-1",
        status=status,
        status_label="status",
        asking_price_nok=10_000,
        conservative_market_value_nok=25_000 if verified else None,
        median_market_value_nok=26_000 if verified else None,
        discount_vs_conservative=0.6 if verified else None,
        discount_vs_median=0.615 if verified else None,
        confidence="high" if verified else "insufficient",
        comparable_count=5 if verified else 0,
        is_verified=verified,
        reasons=(),
        warnings=(),
    )


def _history() -> PriceHistorySummary:
    return PriceHistorySummary(
        opportunity_id="decision-owner-1",
        first_seen_at="2026-07-01T00:00:00+00:00",
        last_seen_at="2026-07-20T00:00:00+00:00",
        first_price_nok=10_000,
        current_price_nok=10_000,
        lowest_price_nok=10_000,
        highest_price_nok=10_000,
        price_change_count=0,
        change_from_first=0,
        age_days=19,
        status="new",
        status_label="new",
        significant_drop=False,
    )


def _seller(risk: str = "low", confidence: str = "high") -> SellerReliabilityReport:
    return SellerReliabilityReport(
        seller_id="seller-1" if confidence != "insufficient" else None,
        seller_name="Seller AS" if confidence != "insufficient" else None,
        seller_type="company" if confidence != "insufficient" else None,
        score=88 if risk == "low" else 30 if risk == "high" else None,
        grade="A" if risk == "low" else "E" if risk == "high" else "U",
        risk=risk,
        risk_label="label",
        confidence=confidence,
        is_verified=risk == "low",
        evidence_count=7 if confidence == "high" else 0,
        reasons=(),
        warnings=(),
    )


def test_high_seller_risk_is_rejected_by_canonical_decision() -> None:
    decision = OpportunityProfitDecisionEngine().decide(
        _value(),
        context=OpportunityDecisionContext(
            market_verification_status="strong_discount",
            market_is_verified=True,
            seller_risk="high",
            seller_confidence="high",
        ),
    )

    assert decision.decision == "reject"
    assert decision.decision_label == "🔴 ارفض"
    assert "seller_risk_high" in decision.blockers


def test_overpriced_market_is_rejected_by_canonical_decision() -> None:
    decision = OpportunityProfitDecisionEngine().decide(
        _value(),
        context=OpportunityDecisionContext(
            market_verification_status="overpriced",
            market_is_verified=True,
            seller_risk="low",
            seller_confidence="high",
        ),
    )

    assert decision.decision == "reject"
    assert "market_overpriced" in decision.blockers


def test_unverified_market_cannot_remain_canonical_buy() -> None:
    decision = OpportunityProfitDecisionEngine().decide(
        _value(),
        context=OpportunityDecisionContext(
            market_verification_status="unavailable",
            market_is_verified=False,
            seller_risk="low",
            seller_confidence="high",
        ),
    )

    assert decision.decision == "monitor"
    assert decision.is_actionable is False
    assert "market_verification_required" in decision.blockers


def test_intelligence_mirrors_canonical_decision_without_second_recommendation() -> None:
    decision = OpportunityProfitDecisionEngine().decide(
        _value(),
        context=OpportunityDecisionContext(
            market_verification_status="overpriced",
            market_is_verified=True,
            seller_risk="high",
            seller_confidence="high",
        ),
    )
    report = OpportunityIntelligenceEngine().explain(
        _opportunity(),
        decision,
        _score(),
        _verification("overpriced", True),
        _history(),
        _seller("high", "high"),
    )

    assert report.recommendation == decision.decision
    assert report.recommendation_label == decision.decision_label
