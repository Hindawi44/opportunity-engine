from opportunity_engine.ods.opportunity_profit import OpportunityProfitDecision
from opportunity_engine.ods.opportunity_scoring import OpportunityScoringEngine
from opportunity_engine.ods.unified_opportunity import UnifiedOpportunity


def _opportunity(*, title="Kontorstoler", missing=(), city="Trondheim", description="Lett å transportere"):
    return UnifiedOpportunity(
        opportunity_id="unified-test-1",
        source_name="test",
        source_document_id="test-1",
        title=title,
        url="https://example.test/1",
        description=description,
        current_price_nok=10_000.0,
        city=city,
        ends_at=None,
        fee_text="10%",
        mva_status="included",
        image_urls=(),
        missing_fields=tuple(missing),
        raw_metadata={},
    )


def _decision(*, decision="buy", profit=12_000.0, roi=0.6, confidence="high", blockers=(), warnings=(), actionable=True):
    labels = {"buy": "🟢 اشترِ", "monitor": "🟡 راقب", "reject": "🔴 ارفض"}
    return OpportunityProfitDecision(
        opportunity_id="unified-test-1",
        decision=decision,
        decision_label=labels[decision],
        conservative_resale_nok=32_000.0,
        total_cost_nok=20_000.0,
        expected_profit_nok=profit,
        roi=roi,
        margin_on_resale=0.375,
        maximum_total_cost_nok=23_000.0,
        maximum_purchase_price_nok=13_000.0,
        confidence=confidence,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        reasons=("reason",),
        is_actionable=actionable,
    )


def test_strong_complete_opportunity_scores_high() -> None:
    score = OpportunityScoringEngine().score(_opportunity(), _decision())
    assert 80 <= score.total_score <= 100
    assert score.grade == "A"
    assert score.financial_score > 30
    assert score.risk_penalty == 0


def test_missing_data_and_blockers_preserve_preliminary_listing_score() -> None:
    score = OpportunityScoringEngine().score(
        _opportunity(missing=("city", "ends_at", "fee_text"), city=None),
        _decision(
            decision="monitor",
            profit=None,
            roi=None,
            confidence="insufficient",
            blockers=("market_comparables", "cost:transport_nok"),
            warnings=("market evidence missing", "transport missing"),
            actionable=False,
        ),
    )
    assert 0 < score.total_score <= 59
    assert score.grade in {"D", "E"}
    assert score.financial_score == 0
    assert score.confidence_score == 0
    assert score.resale_score > 0
    assert score.logistics_score > 0
    assert score.risk_penalty <= 12


def test_many_evidence_blockers_do_not_erase_observable_asset_quality() -> None:
    score = OpportunityScoringEngine().score(
        _opportunity(title="Butikkinnredning og kontorstoler", missing=("ends_at",)),
        _decision(
            decision="monitor",
            profit=None,
            roi=None,
            confidence="insufficient",
            blockers=(
                "market_comparables",
                "total_cost_nok",
                "cost:transport_nok",
                "cost:dismantling_nok",
                "cost:auction_fee_nok",
                "cost:condition_and_missing_parts",
            ),
            warnings=("missing market evidence",) * 10,
            actionable=False,
        ),
    )
    assert score.total_score > 0
    assert score.resale_score >= 13
    assert score.risk_penalty == 12


def test_reject_score_is_capped_below_monitor_threshold() -> None:
    score = OpportunityScoringEngine().score(
        _opportunity(),
        _decision(decision="reject", profit=50_000.0, roi=1.0),
    )
    assert score.total_score <= 39


def test_difficult_logistics_score_lower_than_easy_asset() -> None:
    engine = OpportunityScoringEngine()
    easy = engine.score(_opportunity(), _decision())
    hard = engine.score(
        _opportunity(
            title="Komplett produksjonslinje",
            description="Tung, må demonteres og hentes med lastebil",
        ),
        _decision(),
    )
    assert hard.logistics_score < easy.logistics_score
    assert hard.resale_score < easy.resale_score
