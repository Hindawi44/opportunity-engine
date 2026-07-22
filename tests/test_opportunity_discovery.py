from datetime import datetime, timezone

from opportunity_engine.ods.market_verification import MarketPriceVerification
from opportunity_engine.ods.opportunity_discovery import OpportunityDiscoveryEngine
from opportunity_engine.ods.opportunity_profit import OpportunityProfitDecision
from opportunity_engine.ods.opportunity_scoring import OpportunityScore
from opportunity_engine.ods.price_history import PriceHistorySummary
from opportunity_engine.ods.seller_reliability import SellerReliabilityReport
from opportunity_engine.ods.unified_opportunity import UnifiedOpportunity


def _opportunity() -> UnifiedOpportunity:
    return UnifiedOpportunity(
        opportunity_id="unified-1",
        source_name="Auksjonen.no",
        source_document_id="1",
        title="Butikkinnredning",
        url="https://example.test/1",
        description="Lett demontert butikkinnredning",
        current_price_nok=10_000,
        city="Trondheim",
        ends_at=datetime(2026, 8, 1, 16, 0, tzinfo=timezone.utc),
        fee_text="10%",
        mva_status="included",
        image_urls=(),
        missing_fields=(),
        raw_metadata={},
    )


def _decision(*, decision="buy", blockers=(), actionable=True) -> OpportunityProfitDecision:
    return OpportunityProfitDecision(
        opportunity_id="unified-1",
        decision=decision,
        decision_label="🟢 اشترِ" if decision == "buy" else "🟡 راقب",
        conservative_resale_nok=25_000,
        total_cost_nok=13_000,
        expected_profit_nok=12_000,
        roi=0.9231,
        margin_on_resale=0.48,
        maximum_total_cost_nok=18_500,
        maximum_purchase_price_nok=15_500,
        confidence="high" if actionable else "insufficient",
        blockers=blockers,
        warnings=(),
        reasons=("ربحية قوية",),
        is_actionable=actionable,
    )


def _score(value=90.0) -> OpportunityScore:
    return OpportunityScore(
        opportunity_id="unified-1",
        total_score=value,
        financial_score=40,
        confidence_score=15,
        data_quality_score=15,
        resale_score=15,
        logistics_score=15,
        risk_penalty=0,
        grade="A",
        reasons=(),
    )


def _verification(*, status="strong_discount", verified=True) -> MarketPriceVerification:
    return MarketPriceVerification(
        opportunity_id="unified-1",
        status=status,
        status_label="🟢 خصم سوقي قوي" if status == "strong_discount" else "🔴 أعلى من السوق",
        asking_price_nok=10_000,
        conservative_market_value_nok=25_000,
        median_market_value_nok=26_000,
        discount_vs_conservative=0.60 if status == "strong_discount" else -0.20,
        discount_vs_median=0.6154,
        confidence="high",
        comparable_count=5,
        is_verified=verified,
        reasons=(),
        warnings=(),
    )


def _history(*, drop=False) -> PriceHistorySummary:
    return PriceHistorySummary(
        opportunity_id="unified-1",
        first_seen_at="2026-07-01T00:00:00+00:00",
        last_seen_at="2026-07-20T00:00:00+00:00",
        first_price_nok=12_000,
        current_price_nok=10_000,
        lowest_price_nok=10_000,
        highest_price_nok=12_000,
        price_change_count=1 if drop else 0,
        change_from_first=-0.1667 if drop else 0.0,
        age_days=19,
        status="price_drop" if drop else "new",
        status_label="🟢 انخفض السعر" if drop else "🔵 سعر أولي",
        significant_drop=drop,
    )


def _seller(*, risk="low") -> SellerReliabilityReport:
    return SellerReliabilityReport(
        seller_id="seller-1",
        seller_name="Verified AS",
        seller_type="company",
        score=90 if risk == "low" else 30,
        grade="A" if risk == "low" else "E",
        risk=risk,
        risk_label="🟢 مخاطر بائع منخفضة" if risk == "low" else "🔴 مخاطر بائع مرتفعة",
        confidence="high",
        is_verified=risk == "low",
        evidence_count=7,
        reasons=(),
        warnings=(),
    )


def _unknown_seller() -> SellerReliabilityReport:
    return SellerReliabilityReport(
        seller_id=None,
        seller_name=None,
        seller_type=None,
        score=None,
        grade="U",
        risk="unknown",
        risk_label="⚪ بائع غير متحقق",
        confidence="insufficient",
        is_verified=False,
        evidence_count=0,
        reasons=(),
        warnings=(),
    )


def test_flags_exceptional_verified_opportunity() -> None:
    report = OpportunityDiscoveryEngine().discover(
        _opportunity(), _decision(), _score(), _verification(), _history(drop=True), _seller()
    )

    assert report.discovery_score >= 80
    assert report.tier == "exceptional"
    assert report.is_exceptional is True
    assert report.requires_immediate_review is True
    assert "verified_strong_market_discount" in report.signals
    assert "significant_price_drop" in report.signals


def test_missing_evidence_caps_non_actionable_opportunity() -> None:
    report = OpportunityDiscoveryEngine().discover(
        _opportunity(),
        _decision(decision="monitor", blockers=("market_comparables",), actionable=False),
        _score(55),
        _verification(status="needs_review", verified=False),
        _history(),
        _unknown_seller(),
    )

    assert report.discovery_score <= 59
    assert report.is_exceptional is False
    assert report.tier in {"low", "watch"}
    assert report.warnings


def test_preliminary_score_is_not_erased_by_missing_economics() -> None:
    report = OpportunityDiscoveryEngine().discover(
        _opportunity(),
        _decision(
            decision="monitor",
            blockers=("market_comparables", "cost:transport_nok", "cost:auction_fee_nok"),
            actionable=False,
        ),
        _score(12),
        _verification(status="needs_review", verified=False),
        _history(),
        _unknown_seller(),
    )

    assert report.discovery_score == 12
    assert report.tier == "low"
    assert report.is_exceptional is False
    assert any("فجوات أدلة" in warning for warning in report.warnings)


def test_overpriced_or_high_risk_seller_is_not_exceptional() -> None:
    report = OpportunityDiscoveryEngine().discover(
        _opportunity(), _decision(), _score(), _verification(status="overpriced"), _history(), _seller(risk="high")
    )

    assert report.is_exceptional is False
    assert any("أعلى" in warning or "مرتفعة" in warning for warning in report.warnings)
