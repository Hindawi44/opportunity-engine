"""Evidence scoring for Opportunity Engine v2.5.2.

Scores research evidence from 0 to 100 without changing the underlying facts.
The score measures evidential strength, not investment attractiveness.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable
from urllib.parse import urlparse

from .evidence_store import (
    EvidenceConfidence,
    EvidenceDirection,
    EvidenceType,
    ResearchEvidence,
)


class EvidenceGrade(str, Enum):
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"
    VERY_RELIABLE = "very_reliable"


class SourceTier(str, Enum):
    PRIMARY_OFFICIAL = "primary_official"
    PRIMARY_COMMERCIAL = "primary_commercial"
    SECONDARY_REPUTABLE = "secondary_reputable"
    SECONDARY_UNVERIFIED = "secondary_unverified"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class EvidenceScoreBreakdown:
    source_quality: float
    freshness: float
    completeness: float
    numeric_verifiability: float
    corroboration: float
    source_primacy: float
    scenario_relevance: float

    @property
    def total(self) -> float:
        return round(
            self.source_quality
            + self.freshness
            + self.completeness
            + self.numeric_verifiability
            + self.corroboration
            + self.source_primacy
            + self.scenario_relevance,
            2,
        )


@dataclass(frozen=True, slots=True)
class EvidenceScore:
    evidence_id: str
    score: float
    grade: EvidenceGrade
    source_tier: SourceTier
    breakdown: EvidenceScoreBreakdown
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]


class EvidenceScoringEngine:
    """Deterministically score evidence strength from explicit metadata.

    Maximum points:
    - source quality: 25
    - freshness: 15
    - completeness: 15
    - numeric verifiability: 15
    - corroboration: 15
    - source primacy: 10
    - scenario relevance: 5
    """

    OFFICIAL_DOMAINS = {
        "brreg.no",
        "ssb.no",
        "lovdata.no",
        "regjeringen.no",
        "skatteetaten.no",
        "nav.no",
        "vegvesen.no",
        "politiet.no",
        "namsos.kommune.no",
    }
    PRIMARY_MARKET_DOMAINS = {
        "finn.no",
        "auksjonen.no",
        "konkurs.app",
        "konkurskupp.no",
        "bjaroy.no",
        "bjaroyhandel.no",
    }
    REPUTABLE_SECONDARY_DOMAINS = {
        "proff.no",
        "purehelp.no",
        "dn.no",
        "e24.no",
        "nrk.no",
    }

    def score(
        self,
        evidence: ResearchEvidence,
        *,
        peers: Iterable[ResearchEvidence] = (),
        now: datetime | None = None,
    ) -> EvidenceScore:
        now = now or datetime.now(timezone.utc)
        peer_list = tuple(item for item in peers if item.evidence_id != evidence.evidence_id)
        source_tier = self.classify_source(evidence)
        reasons: list[str] = []
        warnings: list[str] = []

        source_quality = self._source_quality(source_tier, evidence, reasons, warnings)
        freshness = self._freshness(evidence, now, reasons, warnings)
        completeness = self._completeness(evidence, reasons, warnings)
        numeric = self._numeric_verifiability(evidence, reasons)
        corroboration = self._corroboration(evidence, peer_list, reasons)
        primacy = self._source_primacy(source_tier, reasons)
        relevance = self._scenario_relevance(evidence, reasons)

        breakdown = EvidenceScoreBreakdown(
            source_quality=source_quality,
            freshness=freshness,
            completeness=completeness,
            numeric_verifiability=numeric,
            corroboration=corroboration,
            source_primacy=primacy,
            scenario_relevance=relevance,
        )
        score = max(0.0, min(100.0, breakdown.total))
        return EvidenceScore(
            evidence_id=evidence.evidence_id,
            score=score,
            grade=self.grade(score),
            source_tier=source_tier,
            breakdown=breakdown,
            reasons=tuple(reasons),
            warnings=tuple(warnings),
        )

    @staticmethod
    def grade(score: float) -> EvidenceGrade:
        if score < 40:
            return EvidenceGrade.WEAK
        if score < 70:
            return EvidenceGrade.MEDIUM
        if score < 90:
            return EvidenceGrade.STRONG
        return EvidenceGrade.VERY_RELIABLE

    def classify_source(self, evidence: ResearchEvidence) -> SourceTier:
        metadata_tier = str(evidence.metadata.get("source_tier", "")).strip().lower()
        if metadata_tier:
            try:
                return SourceTier(metadata_tier)
            except ValueError:
                pass

        domain = self._domain(evidence.source_url)
        if domain in self.OFFICIAL_DOMAINS or any(domain.endswith(f".{item}") for item in self.OFFICIAL_DOMAINS):
            return SourceTier.PRIMARY_OFFICIAL
        if domain in self.PRIMARY_MARKET_DOMAINS or any(domain.endswith(f".{item}") for item in self.PRIMARY_MARKET_DOMAINS):
            return SourceTier.PRIMARY_COMMERCIAL
        if domain in self.REPUTABLE_SECONDARY_DOMAINS or any(domain.endswith(f".{item}") for item in self.REPUTABLE_SECONDARY_DOMAINS):
            return SourceTier.SECONDARY_REPUTABLE
        if evidence.source_url:
            return SourceTier.SECONDARY_UNVERIFIED
        return SourceTier.UNKNOWN

    @staticmethod
    def _domain(url: str | None) -> str:
        if not url:
            return ""
        return (urlparse(url).hostname or "").lower().removeprefix("www.")

    @staticmethod
    def _source_quality(
        tier: SourceTier,
        evidence: ResearchEvidence,
        reasons: list[str],
        warnings: list[str],
    ) -> float:
        points = {
            SourceTier.PRIMARY_OFFICIAL: 25.0,
            SourceTier.PRIMARY_COMMERCIAL: 22.0,
            SourceTier.SECONDARY_REPUTABLE: 17.0,
            SourceTier.SECONDARY_UNVERIFIED: 9.0,
            SourceTier.UNKNOWN: 4.0,
        }[tier]
        reasons.append(f"Source tier: {tier.value}")
        if evidence.confidence is EvidenceConfidence.HIGH:
            points = min(25.0, points + 2.0)
        elif evidence.confidence is EvidenceConfidence.LOW:
            points = max(0.0, points - 4.0)
            warnings.append("Evidence is marked low confidence")
        return points

    @staticmethod
    def _freshness(
        evidence: ResearchEvidence,
        now: datetime,
        reasons: list[str],
        warnings: list[str],
    ) -> float:
        try:
            observed = datetime.fromisoformat(evidence.updated_at.replace("Z", "+00:00"))
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            age_days = max(0, (now - observed).days)
        except (TypeError, ValueError):
            warnings.append("Evidence update timestamp is invalid")
            return 0.0

        if age_days <= 7:
            points = 15.0
        elif age_days <= 30:
            points = 12.0
        elif age_days <= 90:
            points = 9.0
        elif age_days <= 180:
            points = 6.0
        elif age_days <= 365:
            points = 3.0
        else:
            points = 1.0
            warnings.append("Evidence is more than one year old")
        reasons.append(f"Evidence age: {age_days} days")
        return points

    @staticmethod
    def _completeness(
        evidence: ResearchEvidence,
        reasons: list[str],
        warnings: list[str],
    ) -> float:
        points = 0.0
        if evidence.statement.strip():
            points += 4.0
        if evidence.source_name.strip():
            points += 3.0
        if evidence.source_url:
            points += 3.0
        if evidence.observations:
            points += 3.0
        if evidence.metadata:
            points += 2.0
        if points < 10:
            warnings.append("Evidence record is incomplete")
        reasons.append(f"Completeness: {points}/15")
        return points

    @staticmethod
    def _numeric_verifiability(evidence: ResearchEvidence, reasons: list[str]) -> float:
        observations = evidence.observations
        numeric = [item for item in observations if item.numeric_value is not None]
        if not numeric:
            return 4.0 if evidence.evidence_type not in {EvidenceType.MARKET_PRICE, EvidenceType.COST} else 0.0
        currency_complete = all(item.currency for item in numeric)
        points = 12.0 if currency_complete else 8.0
        if len(numeric) > 1:
            points = min(15.0, points + 3.0)
        reasons.append(f"Numeric observations: {len(numeric)}")
        return points

    @staticmethod
    def _corroboration(
        evidence: ResearchEvidence,
        peers: tuple[ResearchEvidence, ...],
        reasons: list[str],
    ) -> float:
        matching = [
            item
            for item in peers
            if item.opportunity_id == evidence.opportunity_id
            and item.evidence_type is evidence.evidence_type
            and item.source_name.casefold() != evidence.source_name.casefold()
        ]
        if len(matching) >= 2:
            reasons.append("Corroborated by at least two independent sources")
            return 15.0
        if len(matching) == 1:
            reasons.append("Corroborated by one independent source")
            return 10.0
        return 3.0

    @staticmethod
    def _source_primacy(tier: SourceTier, reasons: list[str]) -> float:
        if tier is SourceTier.PRIMARY_OFFICIAL:
            reasons.append("Primary official source")
            return 10.0
        if tier is SourceTier.PRIMARY_COMMERCIAL:
            reasons.append("Primary commercial source")
            return 8.0
        if tier is SourceTier.SECONDARY_REPUTABLE:
            return 5.0
        if tier is SourceTier.SECONDARY_UNVERIFIED:
            return 2.0
        return 0.0

    @staticmethod
    def _scenario_relevance(evidence: ResearchEvidence, reasons: list[str]) -> float:
        if evidence.scenario_ids:
            reasons.append(f"Linked to {len(evidence.scenario_ids)} scenario(s)")
            return 5.0
        if evidence.direction is not EvidenceDirection.NEUTRAL:
            reasons.append(f"Direction: {evidence.direction.value}")
            return 3.0
        return 1.0
