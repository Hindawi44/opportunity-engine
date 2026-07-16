"""Unified, conservative opportunity intelligence scoring.

This module combines only evidence that already exists in ODS. Missing inputs are not
invented; instead they reduce completeness and cap the recommendation.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class UnifiedRecommendation(str, Enum):
    PURSUE = "PURSUE"
    WATCH = "WATCH"
    REJECT = "REJECT"


@dataclass(frozen=True)
class UnifiedIntelligenceInputs:
    internal_score: float
    candidate_confidence: float
    evidence_quality: float | None = None
    market_health: float | None = None
    trend_confidence: float | None = None
    brreg_evidence: float | None = None
    financial_score: float | None = None
    competition_score: float | None = None
    source_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class UnifiedIntelligenceReport:
    ods_score: float
    recommendation: UnifiedRecommendation
    component_scores: tuple[tuple[str, float], ...]
    evidence_completeness: float
    source_count: int
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    blockers: tuple[str, ...]


def build_unified_intelligence(inputs: UnifiedIntelligenceInputs) -> UnifiedIntelligenceReport:
    """Create one grounded ODS score from available normalized evidence."""
    _validate_score("internal_score", inputs.internal_score)
    _validate_score("candidate_confidence", inputs.candidate_confidence)

    optional = {
        "Evidence quality": inputs.evidence_quality,
        "Market health": inputs.market_health,
        "Trend confidence": inputs.trend_confidence,
        "Brreg evidence": inputs.brreg_evidence,
        "Financial potential": inputs.financial_score,
        "Competition": inputs.competition_score,
    }
    for label, value in optional.items():
        if value is not None:
            _validate_score(label, value)

    components: list[tuple[str, float, float]] = [
        ("Internal ranking", inputs.internal_score, 0.30),
        ("Candidate confidence", inputs.candidate_confidence, 0.20),
    ]
    weighted_optional = (
        ("Evidence quality", inputs.evidence_quality, 0.15),
        ("Market health", inputs.market_health, 0.10),
        ("Trend confidence", inputs.trend_confidence, 0.05),
        ("Brreg evidence", inputs.brreg_evidence, 0.10),
        ("Financial potential", inputs.financial_score, 0.07),
        ("Competition", inputs.competition_score, 0.03),
    )
    components.extend((label, value, weight) for label, value, weight in weighted_optional if value is not None)

    available_weight = sum(weight for _, _, weight in components)
    raw_score = sum(value * weight for _, value, weight in components) / available_weight
    completeness = round(available_weight * 100.0, 1)

    sources = tuple(dict.fromkeys(name.strip() for name in inputs.source_names if name.strip()))
    source_count = len(sources)
    source_bonus = min(max(source_count - 1, 0) * 1.5, 4.5)
    missing_penalty = max(0.0, 100.0 - completeness) * 0.08
    ods_score = max(0.0, min(100.0, raw_score + source_bonus - missing_penalty))

    missing = tuple(label for label, value, _ in weighted_optional if value is None)
    strengths = _strengths(components, source_count)
    weaknesses = _weaknesses(components, completeness, source_count)
    blockers = _blockers(inputs, completeness, source_count)
    recommendation = _recommendation(ods_score, completeness, source_count, blockers)

    return UnifiedIntelligenceReport(
        ods_score=round(ods_score, 2),
        recommendation=recommendation,
        component_scores=tuple((label, round(value, 2)) for label, value, _ in components),
        evidence_completeness=completeness,
        source_count=source_count,
        strengths=strengths,
        weaknesses=weaknesses,
        missing_evidence=missing,
        blockers=blockers,
    )


def rank_unified_reports(
    reports: Iterable[tuple[str, UnifiedIntelligenceReport]],
) -> tuple[tuple[int, str, UnifiedIntelligenceReport], ...]:
    ordered = sorted(reports, key=lambda item: (-item[1].ods_score, item[0].casefold()))
    return tuple((index, opportunity_id, report) for index, (opportunity_id, report) in enumerate(ordered, start=1))


def _recommendation(
    score: float,
    completeness: float,
    source_count: int,
    blockers: tuple[str, ...],
) -> UnifiedRecommendation:
    if score >= 80 and completeness >= 85 and source_count >= 2 and not blockers:
        return UnifiedRecommendation.PURSUE
    if score >= 55:
        return UnifiedRecommendation.WATCH
    return UnifiedRecommendation.REJECT


def _strengths(components: list[tuple[str, float, float]], source_count: int) -> tuple[str, ...]:
    values = [f"{label} is strong ({value:.0f}/100)." for label, value, _ in components if value >= 75]
    if source_count >= 2:
        values.append(f"Evidence is supported by {source_count} distinct sources.")
    return tuple(values)


def _weaknesses(
    components: list[tuple[str, float, float]], completeness: float, source_count: int
) -> tuple[str, ...]:
    values = [f"{label} is weak ({value:.0f}/100)." for label, value, _ in components if value < 50]
    if completeness < 85:
        values.append(f"Evidence completeness is only {completeness:.0f}%.")
    if source_count < 2:
        values.append("The opportunity is not yet corroborated by multiple sources.")
    return tuple(values)


def _blockers(
    inputs: UnifiedIntelligenceInputs,
    completeness: float,
    source_count: int,
) -> tuple[str, ...]:
    values: list[str] = []
    if source_count < 2:
        values.append("At least two independent sources are required before PURSUE.")
    if completeness < 85:
        values.append("Evidence completeness must reach 85% before PURSUE.")
    if inputs.financial_score is None:
        values.append("Financial viability has not been validated.")
    if inputs.market_health is None:
        values.append("Market health evidence is missing.")
    return tuple(values)


def _validate_score(name: str, value: float) -> None:
    if not 0.0 <= float(value) <= 100.0:
        raise ValueError(f"{name} must be between 0 and 100")
