"""Conservative market-evidence adjustments for ODS ranking."""

from __future__ import annotations

from dataclasses import dataclass

_CATEGORY_RELEVANCE: dict[str, float] = {
    "inventory": 1.00,
    "returns": 0.85,
    "resale": 0.80,
    "supplier_enablement": 0.75,
    "industry_structure": 0.70,
    "circular_economy": 0.65,
    "fit_data": 0.55,
    "membership": 0.45,
    "logistics": 0.40,
    "compliance_data": 0.35,
}

@dataclass(frozen=True)
class EvidenceAdjustment:
    base_score: float
    adjustment: float
    final_score: float
    evidence_score: float
    relevance: float
    reason: str


def calculate_ssb_adjustment(*, base_score: float, category: str, evidence_score: float, maximum_bonus: float = 3.0) -> EvidenceAdjustment:
    """Apply a bounded source-quality bonus; do not infer market direction."""
    if not 0 <= base_score <= 100:
        raise ValueError("base_score must be between 0 and 100")
    if not 0 <= evidence_score <= 100:
        raise ValueError("evidence_score must be between 0 and 100")
    if not 0 <= maximum_bonus <= 10:
        raise ValueError("maximum_bonus must be between 0 and 10")
    relevance = _CATEGORY_RELEVANCE.get(category, 0.25)
    adjustment = round(maximum_bonus * (evidence_score / 100.0) * relevance, 2)
    final_score = round(min(100.0, base_score + adjustment), 2)
    return EvidenceAdjustment(
        base_score=base_score,
        adjustment=adjustment,
        final_score=final_score,
        evidence_score=evidence_score,
        relevance=relevance,
        reason=("Official SSB evidence availability and category relevance; "
                "no growth, decline, or profitability trend inferred."),
    )
