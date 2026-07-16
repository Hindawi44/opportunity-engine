import pytest

from opportunity_engine.ods.confidence import (
    BrregEvidenceSummary,
    calculate_opportunity_confidence,
    summarize_brreg_entities,
)


def test_summarize_brreg_entities_counts_status_and_municipalities():
    summary = summarize_brreg_entities([
        {"konkurs": False, "underAvvikling": False, "forretningsadresse": {"kommune": "NAMSOS"}},
        {"konkurs": True, "underAvvikling": False, "forretningsadresse": {"kommune": "TRONDHEIM"}},
        {"konkurs": False, "underAvvikling": True, "forretningsadresse": {"kommune": "NAMSOS"}},
    ])
    assert summary.entity_count == 3
    assert summary.bankrupt_count == 1
    assert summary.liquidation_count == 1
    assert summary.municipalities == ("NAMSOS", "TRONDHEIM")
    assert 0 <= summary.evidence_score <= 100


def test_confidence_renormalizes_when_sources_are_missing():
    result = calculate_opportunity_confidence(
        internal_score=72,
        candidate_confidence=0.8,
        validation_readiness=65,
    )
    assert 0 <= result.final_score <= 100
    assert set(result.missing_evidence) == {
        "SSB evidence",
        "SSB trend intelligence",
        "Brreg business structure",
    }


def test_confidence_combines_all_sources_transparently():
    result = calculate_opportunity_confidence(
        internal_score=78,
        candidate_confidence=0.82,
        validation_readiness=72,
        ssb_evidence_score=90,
        market_health_score=76,
        trend_confidence=80,
        brreg=BrregEvidenceSummary(
            entity_count=20,
            bankrupt_count=1,
            liquidation_count=0,
            municipalities=("NAMSOS", "TRONDHEIM"),
            evidence_score=85,
        ),
    )
    assert result.final_score >= 70
    assert result.decision_band in {"strong", "promising"}
    assert not result.missing_evidence
    assert dict(result.component_scores)["ssb_evidence"] == 90


def test_brreg_pressure_reduces_structure_component():
    healthy = calculate_opportunity_confidence(
        internal_score=70,
        candidate_confidence=0.7,
        validation_readiness=70,
        brreg=BrregEvidenceSummary(10, 0, 0, (), 80),
    )
    pressured = calculate_opportunity_confidence(
        internal_score=70,
        candidate_confidence=0.7,
        validation_readiness=70,
        brreg=BrregEvidenceSummary(10, 3, 2, (), 80),
    )
    assert dict(pressured.component_scores)["brreg_structure"] < dict(healthy.component_scores)["brreg_structure"]


def test_invalid_scores_are_rejected():
    with pytest.raises(ValueError):
        calculate_opportunity_confidence(
            internal_score=101,
            candidate_confidence=0.5,
            validation_readiness=50,
        )
