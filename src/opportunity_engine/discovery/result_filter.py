"""Deterministic pre-classification filter for noisy web search results."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from opportunity_engine.discovery.models import DiscoveryCandidate


@dataclass(frozen=True)
class FilterDecision:
    keep: bool
    reason: str
    score: int


_INFORMATION_TERMS = (
    "ordbok", "ordliste", "synonym", "definisjon", "hva er", "wiki",
    "wikipedia", "guide", "artikkel", "blogg", "nyheter", "lovdata",
    "rettigheter", "regelverk", "podcast", "youtube", "facebook",
)

_SALE_TERMS = (
    "til salgs", "selges", "auksjon", "budrunde", "opphørssalg",
    "tømmesalg", "lagersalg", "varelager", "vareparti", "konkursbo",
    "avvikling", "restlager", "overskuddslager", "butikkinnredning",
    "lager ryddes", "hele lageret", "komplett lager",
)

_COMMERCIAL_TERMS = (
    "butikk", "grossist", "importør", "forhandler", "lager", "parti",
    "brudesalong", "klesbutikk", "firma", "bedrift",
)

_TRUSTED_DOMAIN_HINTS = (
    "auksjon", "auction", "konkurs", "finn.no", "lager", "boauksjon",
    "nettauksjon", "restlager", "avvikling",
)


def _normalized(candidate: DiscoveryCandidate) -> str:
    return " ".join(f"{candidate.title} {candidate.text}".lower().split())


def evaluate_candidate(candidate: DiscoveryCandidate) -> FilterDecision:
    """Return a conservative keep/drop decision before classification."""
    text = _normalized(candidate)
    host = urlparse(candidate.url).netloc.lower()

    if any(term in text or term in host for term in _INFORMATION_TERMS):
        return FilterDecision(False, "informational or dictionary page", -10)

    score = 0
    sale_hits = sum(term in text for term in _SALE_TERMS)
    commercial_hits = sum(term in text for term in _COMMERCIAL_TERMS)
    trusted_hits = sum(term in host for term in _TRUSTED_DOMAIN_HINTS)

    score += sale_hits * 3
    score += commercial_hits * 2
    score += trusted_hits * 2

    if candidate.price_nok is not None:
        score += 2
    if candidate.quantity is not None:
        score += 2
    if candidate.contact:
        score += 1

    if sale_hits == 0:
        return FilterDecision(False, "no public sale signal", score)
    if commercial_hits == 0 and trusted_hits == 0:
        return FilterDecision(False, "sale signal lacks commercial inventory context", score)

    return FilterDecision(True, "commercial sale candidate", score)
