"""Deterministic ranking stage for ODS alpha.

The ranking plugin consumes discovery candidates, applies explicit weighted rules,
and returns a stable shortlist. It does not modify or expand opportunities.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import ODSSession, OpportunityCandidate, Stage, StageResult, Status


@dataclass(frozen=True)
class RankingWeights:
    """Weights for the alpha opportunity score. Values must sum to 1.0."""

    confidence: float = 0.30
    evidence: float = 0.20
    feasibility: float = 0.20
    scalability: float = 0.15
    asset_potential: float = 0.15

    def __post_init__(self) -> None:
        values = (
            self.confidence,
            self.evidence,
            self.feasibility,
            self.scalability,
            self.asset_potential,
        )
        if any(value < 0 for value in values):
            raise ValueError("ranking weights must not be negative")
        if abs(sum(values) - 1.0) > 1e-9:
            raise ValueError("ranking weights must sum to 1.0")


@dataclass(frozen=True)
class RankedOpportunity:
    """An unchanged opportunity plus its transparent ranking result."""

    opportunity: OpportunityCandidate
    final_score: float
    component_scores: tuple[tuple[str, float], ...]
    rank: int

    def __post_init__(self) -> None:
        if not 0.0 <= self.final_score <= 100.0:
            raise ValueError("final_score must be between 0 and 100")
        if self.rank < 1:
            raise ValueError("rank must be at least 1")


_CATEGORY_PROFILES: dict[str, tuple[float, float, float]] = {
    # feasibility, scalability, asset potential
    "industry_structure": (0.72, 0.70, 0.68),
    "supplier_enablement": (0.66, 0.82, 0.80),
    "inventory": (0.58, 0.84, 0.82),
    "circular_economy": (0.55, 0.78, 0.76),
    "fit_data": (0.62, 0.86, 0.90),
    "returns": (0.76, 0.74, 0.70),
    "compliance_data": (0.60, 0.80, 0.84),
    "resale": (0.64, 0.82, 0.78),
    "membership": (0.80, 0.66, 0.62),
    "logistics": (0.48, 0.74, 0.72),
}
_DEFAULT_PROFILE = (0.50, 0.50, 0.50)


class OpportunityRankingPlugin:
    """Ranks discovery candidates using fixed, auditable alpha rules."""

    name = "opportunity_ranking"
    stage = Stage.RANKING

    def __init__(
        self,
        *,
        shortlist_size: int = 5,
        minimum_score: float = 0.0,
        weights: RankingWeights | None = None,
    ) -> None:
        if shortlist_size < 1:
            raise ValueError("shortlist_size must be at least 1")
        if not 0.0 <= minimum_score <= 100.0:
            raise ValueError("minimum_score must be between 0 and 100")
        self.shortlist_size = shortlist_size
        self.minimum_score = minimum_score
        self.weights = weights or RankingWeights()

    def run(self, session: ODSSession) -> StageResult:
        discovery_result = session.results.get(Stage.DISCOVERY)
        if discovery_result is None:
            return self._failure("ranking requires a completed discovery result")
        if discovery_result.status is not Status.COMPLETED:
            return self._failure("ranking requires discovery status completed")

        payload = discovery_result.payload
        if not isinstance(payload, (tuple, list)) or not payload:
            return self._failure("ranking requires a non-empty opportunity list")
        if not all(isinstance(item, OpportunityCandidate) for item in payload):
            return self._failure("discovery payload contains invalid opportunity objects")

        scored = [self._score(candidate) for candidate in payload]
        scored.sort(
            key=lambda item: (
                -item[0],
                -item[1].confidence,
                item[1].opportunity_id,
            )
        )

        shortlisted = [item for item in scored if item[0] >= self.minimum_score]
        shortlisted = shortlisted[: self.shortlist_size]
        ranked = tuple(
            RankedOpportunity(
                opportunity=candidate,
                final_score=score,
                component_scores=components,
                rank=index,
            )
            for index, (score, candidate, components) in enumerate(shortlisted, start=1)
        )

        return StageResult(
            stage=self.stage,
            status=Status.COMPLETED,
            payload=ranked,
            evidence=[
                f"ranking_candidates_received:{len(payload)}",
                f"ranking_shortlist_created:{len(ranked)}",
                "ranking_method:weighted-deterministic-alpha",
            ],
        )

    def _score(
        self, candidate: OpportunityCandidate
    ) -> tuple[float, OpportunityCandidate, tuple[tuple[str, float], ...]]:
        feasibility, scalability, asset_potential = _CATEGORY_PROFILES.get(
            candidate.category, _DEFAULT_PROFILE
        )
        evidence_score = min(len(candidate.evidence) / 3.0, 1.0)

        components = (
            ("confidence", candidate.confidence),
            ("evidence", evidence_score),
            ("feasibility", feasibility),
            ("scalability", scalability),
            ("asset_potential", asset_potential),
        )
        weighted = (
            candidate.confidence * self.weights.confidence
            + evidence_score * self.weights.evidence
            + feasibility * self.weights.feasibility
            + scalability * self.weights.scalability
            + asset_potential * self.weights.asset_potential
        )
        return round(weighted * 100.0, 2), candidate, components

    def _failure(self, message: str) -> StageResult:
        return StageResult(
            stage=self.stage,
            status=Status.FAILED,
            errors=[message],
        )
