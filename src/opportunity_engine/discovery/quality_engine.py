"""Deterministic opportunity-quality scoring for Discovery V1.6."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from opportunity_engine.discovery.models import DiscoveryResult


@dataclass(frozen=True, slots=True)
class QualityAssessment:
    score: int
    band: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {"score": self.score, "band": self.band, "reasons": list(self.reasons)}


_TRUSTED_DOMAIN_HINTS = (
    "auksjon", "auction", "konkurs", "finn.no", "boauksjon",
    "nettauksjon", "restlager", "avvikling",
)


def assess_quality(result: DiscoveryResult) -> QualityAssessment:
    """Score one classified result from 0 to 100 without inventing evidence."""
    candidate = result.candidate
    host = urlparse(candidate.url).netloc.casefold()
    reasons: list[str] = []
    score = 0

    if result.status == "SALE_CONFIRMED":
        score += 30
        reasons.append("confirmed public sale signal")
    elif result.status == "CONTACT_REQUIRED":
        score += 15
        reasons.append("commercial lead requires contact")

    if result.category:
        score += 20
        reasons.append(f"textile-sector category: {result.category}")

    if len(candidate.text.strip()) >= 40:
        score += 15
        reasons.append("useful public description")
    elif candidate.text.strip():
        score += 7
        reasons.append("short public description")

    if candidate.price_nok is not None:
        score += 10
        reasons.append("price available")
    if candidate.location:
        score += 10
        reasons.append("location available")
    if any(term in host for term in _TRUSTED_DOMAIN_HINTS):
        score += 10
        reasons.append("commercial or auction domain signal")
    if result.evidence and candidate.title.strip() and candidate.text.strip():
        score += 5
        reasons.append("multiple public evidence fields")

    score = max(0, min(100, score))
    band = "HIGH" if score >= 90 else "REVIEW" if score >= 70 else "LOW"
    return QualityAssessment(score=score, band=band, reasons=tuple(reasons))
