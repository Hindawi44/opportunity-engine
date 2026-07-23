from datetime import datetime, timedelta, timezone

from opportunity_engine.evidence_scoring import (
    EvidenceGrade,
    EvidenceScoringEngine,
    SourceTier,
)
from opportunity_engine.evidence_store import (
    EvidenceConfidence,
    EvidenceDirection,
    EvidenceType,
    ResearchEvidence,
)


def _evidence(**kwargs):
    defaults = dict(
        opportunity_id="unified-123",
        evidence_type=EvidenceType.MARKET_PRICE,
        statement="Verified asking price is 100000 NOK",
        source_name="Auksjonen.no",
        source_url="https://www.auksjonen.no/item/123",
        confidence=EvidenceConfidence.HIGH,
        direction=EvidenceDirection.SUPPORTS,
        scenario_ids=["generated-purchase"],
        numeric_value=100000,
        currency="NOK",
        metadata={"verified": True},
    )
    defaults.update(kwargs)
    return ResearchEvidence.create(**defaults)


def test_scores_recent_primary_numeric_evidence_as_strong_or_better():
    evidence = _evidence()
    result = EvidenceScoringEngine().score(
        evidence,
        now=datetime.now(timezone.utc),
    )

    assert result.score >= 70
    assert result.grade in {EvidenceGrade.STRONG, EvidenceGrade.VERY_RELIABLE}
    assert result.source_tier is SourceTier.PRIMARY_COMMERCIAL
    assert result.breakdown.numeric_verifiability >= 12


def test_official_source_can_reach_very_reliable_with_corroboration():
    evidence = _evidence(
        source_name="Brønnøysundregistrene",
        source_url="https://www.brreg.no/company/123",
        evidence_type=EvidenceType.SELLER,
    )
    peer_a = _evidence(
        source_name="Proff",
        source_url="https://www.proff.no/company/123",
        evidence_type=EvidenceType.SELLER,
    )
    peer_b = _evidence(
        source_name="Purehelp",
        source_url="https://www.purehelp.no/company/123",
        evidence_type=EvidenceType.SELLER,
    )

    result = EvidenceScoringEngine().score(evidence, peers=[peer_a, peer_b])

    assert result.source_tier is SourceTier.PRIMARY_OFFICIAL
    assert result.grade is EvidenceGrade.VERY_RELIABLE
    assert result.breakdown.corroboration == 15


def test_old_unverified_incomplete_evidence_is_weak():
    evidence = ResearchEvidence.create(
        opportunity_id="unified-123",
        evidence_type=EvidenceType.OTHER,
        statement="Possible buyer mentioned in a forum",
        source_name="Unknown forum",
        source_url="https://example.com/post/1",
        confidence=EvidenceConfidence.LOW,
    )
    evidence.updated_at = (datetime.now(timezone.utc) - timedelta(days=800)).isoformat()
    evidence.metadata = {}

    result = EvidenceScoringEngine().score(evidence)

    assert result.grade is EvidenceGrade.WEAK
    assert result.score < 40
    assert result.source_tier is SourceTier.SECONDARY_UNVERIFIED
    assert result.warnings


def test_missing_numeric_value_is_not_treated_as_zero_or_verified():
    evidence = _evidence(numeric_value=None, currency=None)

    result = EvidenceScoringEngine().score(evidence)

    assert result.breakdown.numeric_verifiability == 0
    assert result.score < 100


def test_source_tier_can_be_explicitly_overridden_by_metadata():
    evidence = _evidence(
        source_url="https://example.com/report",
        metadata={"source_tier": "secondary_reputable"},
    )

    result = EvidenceScoringEngine().score(evidence)

    assert result.source_tier is SourceTier.SECONDARY_REPUTABLE


def test_direction_does_not_inflate_evidence_strength_beyond_relevance():
    neutral = _evidence(direction=EvidenceDirection.NEUTRAL, scenario_ids=[])
    weakening = _evidence(direction=EvidenceDirection.WEAKENS, scenario_ids=[])

    neutral_score = EvidenceScoringEngine().score(neutral).score
    weakening_score = EvidenceScoringEngine().score(weakening).score

    assert weakening_score - neutral_score == 2


def test_grade_boundaries_are_exact():
    engine = EvidenceScoringEngine()

    assert engine.grade(0) is EvidenceGrade.WEAK
    assert engine.grade(39.99) is EvidenceGrade.WEAK
    assert engine.grade(40) is EvidenceGrade.MEDIUM
    assert engine.grade(69.99) is EvidenceGrade.MEDIUM
    assert engine.grade(70) is EvidenceGrade.STRONG
    assert engine.grade(89.99) is EvidenceGrade.STRONG
    assert engine.grade(90) is EvidenceGrade.VERY_RELIABLE
    assert engine.grade(100) is EvidenceGrade.VERY_RELIABLE
