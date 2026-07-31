"""Deterministic pre-classification filter for noisy web search results."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from opportunity_engine.discovery.models import DiscoveryCandidate
from opportunity_engine.discovery.textile_taxonomy import classify_textile_opportunity


@dataclass(frozen=True)
class FilterDecision:
    keep: bool
    reason: str
    score: int


_INFORMATION_TERMS = (
    "ordbok", "ordliste", "synonym", "definisjon", "hva er", "wiki",
    "wikipedia", "guide", "artikkel", "blogg", "lovdata",
    "rettigheter", "regelverk", "podcast", "youtube", "facebook",
)

_COMMERCIAL_EVENT_TERMS = (
    "til salgs", "selges", "auksjon", "budrunde", "opphørssalg",
    "tømmesalg", "lagersalg", "varelager", "vareparti", "konkursbo",
    "konkurs", "avvikling", "avvikles", "restlager", "overskuddslager",
    "butikkinnredning", "lager ryddes", "hele lageret", "komplett lager",
    "opphør", "stenger", "legges ned", "tvangsavvikling",
)

_COMMERCIAL_TERMS = (
    "butikk", "grossist", "importør", "forhandler", "lager", "parti",
    "brudesalong", "klesbutikk", "stoffbutikk", "skobutikk", "kleskjede",
    "systue", "skredder", "skredderverksted", "sømverksted",
    "klesproduksjon", "tekstilfabrikk", "firma", "bedrift",
)

_TRUSTED_DOMAIN_HINTS = (
    "auksjon", "auction", "konkurs", "finn.no", "lager", "boauksjon",
    "nettauksjon", "restlager", "avvikling",
)


def _normalized(candidate: DiscoveryCandidate) -> str:
    return " ".join(f"{candidate.title} {candidate.text}".casefold().split())


def evaluate_candidate(candidate: DiscoveryCandidate) -> FilterDecision:
    """Return a conservative keep/drop decision before classification."""
    text = _normalized(candidate)
    host = urlparse(candidate.url).netloc.casefold()

    if any(term in text or term in host for term in _INFORMATION_TERMS):
        return FilterDecision(False, "informational or dictionary page", -10)

    taxonomy = classify_textile_opportunity(candidate.title, candidate.text)
    event_hits = sum(term in text for term in _COMMERCIAL_EVENT_TERMS)
    commercial_hits = sum(term in text for term in _COMMERCIAL_TERMS)
    trusted_hits = sum(term in host for term in _TRUSTED_DOMAIN_HINTS)

    score = event_hits * 3 + commercial_hits * 2 + trusted_hits * 2
    if taxonomy.status == "IN_SCOPE":
        score += 6
    if candidate.price_nok is not None:
        score += 2
    if candidate.quantity is not None:
        score += 2
    if candidate.contact:
        score += 1

    if taxonomy.status != "IN_SCOPE":
        return FilterDecision(False, taxonomy.reason, score)
    if event_hits == 0 and not taxonomy.event_signals:
        return FilterDecision(False, "no public commercial event or sale signal", score)

    reason = (
        "textile-sector early signal"
        if not any(term in text for term in ("til salgs", "selges", "auksjon", "budrunde"))
        else "textile-sector sale candidate"
    )
    return FilterDecision(True, reason, score)
