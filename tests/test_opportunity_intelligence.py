from opportunity_engine.ods.market_verification import MarketPriceVerification
from opportunity_engine.ods.opportunity_intelligence import OpportunityIntelligenceEngine
from opportunity_engine.ods.opportunity_profit import OpportunityProfitDecision
from opportunity_engine.ods.opportunity_scoring import OpportunityScore
from opportunity_engine.ods.price_history import PriceHistorySummary
from opportunity_engine.ods.seller_reliability import SellerReliabilityReport
from opportunity_engine.ods.unified_opportunity import UnifiedOpportunity


def _opportunity() -> UnifiedOpportunity:
    return UnifiedOpportunity(
        opportunity_id="opp-1",
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


def _decision(decision: str = "buy", *, blockers=(), warnings=()) -> OpportunityProfitDecision:
    return OpportunityProfitDecision(
        opportunity_id="opp-1",
        decision=decision,
        decision_label={"buy": "🟢 اشترِ", "monitor": "🟡 راقب", "reject": "🔴 ارفض"}[decision],
        conservative_resale_nok=25_000,
        total_cost_nok=13_000,
        expected_profit_nok=12_000 if decision != "reject" else -1_000,
        roi=0.92 if decision != "reject" else -0.05,
        margin_on_resale=0.48,
        maximum_total_cost_nok=18_500,
        maximum_purchase_price_nok=15_500,
        confidence="high" if not blockers else "insufficient",
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        reasons=("reason",),
        is_actionable=not blockers,
    )


def _score() -> OpportunityScore:
    return OpportunityScore(
        opportunity_id="opp-1",
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
        opportunity_id="opp-1",
        status=status,
        status_label="🟢 خصم سوقي قوي" if verified else "⚪ سوق غير متحقق",
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


def _history(significant_drop: bool = False) -> PriceHistorySummary:
    return PriceHistorySummary(
        opportunity_id="opp-1",
        first_seen_at="2026-07-01T00:00:00+00:00",
        last_seen_at="2026-07-20T00:00:00+00:00",
        first_price_nok=12_000 if significant_drop else 10_000,
        current_price_nok=10_000,
        lowest_price_nok=10_000,
        highest_price_nok=12_000 if significant_drop else 10_000,
        price_change_count=1 if significant_drop else 0,
        change_from_first=-0.1667 if significant_drop else 0,
        age_days=19,
        status="price_drop" if significant_drop else "new",
        status_label="🟢 انخفض السعر" if significant_drop else "🔵 سعر أولي",
        significant_drop=significant_drop,
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


def test_explains_strong_buy_with_auditable_actions() -> None:
    report = OpportunityIntelligenceEngine().explain(
        _opportunity(), _decision(), _score(), _verification(), _history(True), _seller()
    )

    assert report.recommendation == "buy"
    assert report.confidence == "high"
    assert report.is_actionable is True
    assert any("الربح" in item for item in report.strengths)
    assert any("عدم تجاوز" in item for item in report.next_actions)
    assert "88/100" in report.headline


def test_missing_market_and_seller_evidence_forces_monitor() -> None:
    report = OpportunityIntelligenceEngine().explain(
        _opportunity(),
        _decision("monitor", blockers=("market_comparables", "cost:transport_nok")),
        _score(),
        _verification("unavailable", False),
        _history(),
        _seller("unknown", "insufficient"),
    )

    assert report.recommendation == "monitor"
    assert report.confidence == "insufficient"
    assert report.is_actionable is False
    assert report.missing_evidence
    assert any("البائع" in item for item in report.missing_evidence)


def test_high_risk_seller_or_overpriced_market_forces_reject() -> None:
    report = OpportunityIntelligenceEngine().explain(
        _opportunity(),
        _decision(),
        _score(),
        _verification("overpriced", True),
        _history(),
        _seller("high", "high"),
    )

    assert report.recommendation == "reject"
    assert any("البائع" in item for item in report.risks)
    assert "لا تحقق" in report.headline
