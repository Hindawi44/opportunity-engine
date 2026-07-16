"""Transparent multi-source confidence scoring for ODS opportunities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Any


@dataclass(frozen=True)
class BrregEvidenceSummary:
    entity_count: int
    bankrupt_count: int
    liquidation_count: int
    municipalities: tuple[str, ...]
    evidence_score: float

    def __post_init__(self) -> None:
        if self.entity_count < 0 or self.bankrupt_count < 0 or self.liquidation_count < 0:
            raise ValueError("Brreg counts must not be negative")
        if self.bankrupt_count > self.entity_count or self.liquidation_count > self.entity_count:
            raise ValueError("Brreg status counts cannot exceed entity_count")
        if not 0.0 <= self.evidence_score <= 100.0:
            raise ValueError("Brreg evidence_score must be between 0 and 100")


@dataclass(frozen=True)
class OpportunityConfidence:
    final_score: float
    decision_band: str
    component_scores: tuple[tuple[str, float], ...]
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    missing_evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        if not 0.0 <= self.final_score <= 100.0:
            raise ValueError("final_score must be between 0 and 100")


def summarize_brreg_entities(entities: Iterable[Mapping[str, Any]]) -> BrregEvidenceSummary:
    rows = tuple(entities)
    bankrupt_count = sum(bool(row.get("konkurs")) for row in rows)
    liquidation_count = sum(bool(row.get("underAvvikling")) for row in rows)
    municipalities = sorted({
        str(address.get("kommune")).strip()
        for row in rows
        if isinstance((address := row.get("forretningsadresse")), Mapping)
        and address.get("kommune")
    })
    count = len(rows)
    score = min(100.0, 35.0 + min(count, 20) * 2.0 + min(len(municipalities), 10) * 2.5)
    return BrregEvidenceSummary(
        entity_count=count,
        bankrupt_count=bankrupt_count,
        liquidation_count=liquidation_count,
        municipalities=tuple(municipalities),
        evidence_score=round(score, 2),
    )


def calculate_opportunity_confidence(
    *,
    internal_score: float,
    candidate_confidence: float,
    validation_readiness: float,
    ssb_evidence_score: float | None = None,
    market_health_score: float | None = None,
    trend_confidence: float | None = None,
    brreg: BrregEvidenceSummary | None = None,
) -> OpportunityConfidence:
    """Combine independent signals without treating missing data as negative evidence."""
    for name, value in {
        "internal_score": internal_score,
        "validation_readiness": validation_readiness,
    }.items():
        if not 0.0 <= value <= 100.0:
            raise ValueError(f"{name} must be between 0 and 100")
    if not 0.0 <= candidate_confidence <= 1.0:
        raise ValueError("candidate_confidence must be between 0 and 1")

    components: list[tuple[str, float, float]] = [
        ("internal_ranking", internal_score, 0.34),
        ("candidate_confidence", candidate_confidence * 100.0, 0.18),
        ("validation_readiness", validation_readiness, 0.18),
    ]
    missing: list[str] = []

    if ssb_evidence_score is None:
        missing.append("SSB evidence")
    else:
        _validate_optional_score("ssb_evidence_score", ssb_evidence_score)
        components.append(("ssb_evidence", ssb_evidence_score, 0.10))

    if market_health_score is None or trend_confidence is None:
        missing.append("SSB trend intelligence")
    else:
        _validate_optional_score("market_health_score", market_health_score)
        _validate_optional_score("trend_confidence", trend_confidence)
        trend_component = market_health_score * 0.65 + trend_confidence * 0.35
        components.append(("market_trend", trend_component, 0.10))

    if brreg is None:
        missing.append("Brreg business structure")
    else:
        pressure_rate = (brreg.bankrupt_count + brreg.liquidation_count) / max(brreg.entity_count, 1)
        structure_score = max(0.0, brreg.evidence_score - min(25.0, pressure_rate * 100.0))
        components.append(("brreg_structure", structure_score, 0.10))

    total_weight = sum(weight for _, _, weight in components)
    final_score = round(sum(score * weight for _, score, weight in components) / total_weight, 2)
    component_scores = tuple((name, round(score, 2)) for name, score, _ in components)

    strengths = tuple(
        _strength_label(name, score) for name, score in component_scores if score >= 70.0
    )
    weaknesses = tuple(
        _weakness_label(name, score) for name, score in component_scores if score < 50.0
    )
    band = "strong" if final_score >= 75 else "promising" if final_score >= 60 else "uncertain" if final_score >= 45 else "weak"

    return OpportunityConfidence(
        final_score=final_score,
        decision_band=band,
        component_scores=component_scores,
        strengths=strengths,
        weaknesses=weaknesses,
        missing_evidence=tuple(missing),
    )


def _validate_optional_score(name: str, value: float) -> None:
    if not 0.0 <= value <= 100.0:
        raise ValueError(f"{name} must be between 0 and 100")


def _strength_label(name: str, score: float) -> str:
    labels = {
        "internal_ranking": "Strong internal opportunity fit",
        "candidate_confidence": "High discovery confidence",
        "validation_readiness": "Validation plan is actionable",
        "ssb_evidence": "Strong official statistical evidence",
        "market_trend": "Supportive market trend signal",
        "brreg_structure": "Useful official business-register coverage",
    }
    return f"{labels.get(name, name)} ({score:.0f}/100)"


def _weakness_label(name: str, score: float) -> str:
    labels = {
        "internal_ranking": "Weak internal opportunity fit",
        "candidate_confidence": "Low discovery confidence",
        "validation_readiness": "Validation plan is not ready",
        "ssb_evidence": "Limited official statistical evidence",
        "market_trend": "Weak or uncertain market trend",
        "brreg_structure": "Limited or pressured business structure evidence",
    }
    return f"{labels.get(name, name)} ({score:.0f}/100)"
