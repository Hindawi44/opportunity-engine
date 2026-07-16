from opportunity_engine.ods.unified_intelligence import (
    UnifiedIntelligenceInputs,
    UnifiedRecommendation,
    build_unified_intelligence,
    rank_unified_reports,
)


def test_complete_multi_source_case_can_pursue() -> None:
    report = build_unified_intelligence(
        UnifiedIntelligenceInputs(
            internal_score=90,
            candidate_confidence=88,
            evidence_quality=92,
            market_health=84,
            trend_confidence=80,
            brreg_evidence=90,
            financial_score=86,
            competition_score=78,
            source_names=("SSB", "Brreg", "FINN"),
        )
    )
    assert report.ods_score >= 80
    assert report.recommendation is UnifiedRecommendation.PURSUE
    assert report.evidence_completeness == 100
    assert report.source_count == 3
    assert not report.blockers


def test_missing_financial_and_single_source_caps_at_watch() -> None:
    report = build_unified_intelligence(
        UnifiedIntelligenceInputs(
            internal_score=92,
            candidate_confidence=90,
            evidence_quality=95,
            brreg_evidence=90,
            source_names=("Brreg",),
        )
    )
    assert report.recommendation is UnifiedRecommendation.WATCH
    assert "Financial potential" in report.missing_evidence
    assert any("two independent sources" in item for item in report.blockers)


def test_weak_scores_reject() -> None:
    report = build_unified_intelligence(
        UnifiedIntelligenceInputs(
            internal_score=35,
            candidate_confidence=40,
            source_names=("Brreg",),
        )
    )
    assert report.recommendation is UnifiedRecommendation.REJECT


def test_ranking_is_deterministic() -> None:
    high = build_unified_intelligence(
        UnifiedIntelligenceInputs(80, 80, evidence_quality=80, source_names=("A", "B"))
    )
    low = build_unified_intelligence(
        UnifiedIntelligenceInputs(60, 60, evidence_quality=60, source_names=("A", "B"))
    )
    ranked = rank_unified_reports((("low", low), ("high", high)))
    assert ranked[0][1] == "high"
    assert ranked[1][1] == "low"


def test_scores_must_be_normalized() -> None:
    try:
        build_unified_intelligence(UnifiedIntelligenceInputs(101, 50))
    except ValueError as exc:
        assert "between 0 and 100" in str(exc)
    else:
        raise AssertionError("expected ValueError")
