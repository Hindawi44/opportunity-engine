"""Conservative evidence enrichment for live ODS opportunities.

The module scores only evidence that is explicitly present. It never infers asset
availability, market prices, or profit from a Brreg status lead.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .live_feed import FeedItem


class EvidenceBand(str, Enum):
    WEAK = "WEAK"
    PARTIAL = "PARTIAL"
    STRONG = "STRONG"


@dataclass(frozen=True)
class EvidenceFact:
    source: str
    kind: str
    value: str
    weight: float


@dataclass(frozen=True)
class EnrichedOpportunity:
    item: FeedItem
    facts: tuple[EvidenceFact, ...]
    evidence_score: float
    completeness: float
    independent_sources: int
    band: EvidenceBand
    missing_evidence: tuple[str, ...]
    blockers: tuple[str, ...]


def enrich_feed_item(item: FeedItem) -> EnrichedOpportunity:
    facts = tuple(_facts(item.evidence))
    sources = {fact.source for fact in facts}
    raw_score = min(100.0, sum(fact.weight for fact in facts))

    required = {
        "official_status": any(f.kind == "official_status" for f in facts),
        "identity": any(f.kind == "organisation_number" for f in facts),
        "location": any(f.kind == "municipality" for f in facts),
        "market_price": any(f.kind == "market_price" for f in facts),
        "asset_listing": any(f.kind == "asset_listing" for f in facts),
        "financials": any(f.kind == "financials" for f in facts),
    }
    completeness = round(sum(required.values()) / len(required) * 100.0, 1)

    missing = []
    if not required["market_price"]:
        missing.append("Comparable market-price evidence")
    if not required["asset_listing"]:
        missing.append("Verified asset or inventory listing")
    if not required["financials"]:
        missing.append("Documented costs and resale assumptions")

    blockers = []
    if not required["asset_listing"]:
        blockers.append("Do not assume the company has assets available for sale")
    if not required["market_price"] or not required["financials"]:
        blockers.append("Do not estimate profit until price and cost evidence is documented")
    if len(sources) < 2:
        blockers.append("A second independent source is required before a strong recommendation")

    if raw_score >= 75 and completeness >= 70 and len(sources) >= 2:
        band = EvidenceBand.STRONG
    elif raw_score >= 40:
        band = EvidenceBand.PARTIAL
    else:
        band = EvidenceBand.WEAK

    return EnrichedOpportunity(
        item=item,
        facts=facts,
        evidence_score=round(raw_score, 1),
        completeness=completeness,
        independent_sources=len(sources),
        band=band,
        missing_evidence=tuple(missing),
        blockers=tuple(blockers),
    )


def enrich_feed(items: Iterable[FeedItem]) -> tuple[EnrichedOpportunity, ...]:
    enriched = [enrich_feed_item(item) for item in items]
    return tuple(sorted(enriched, key=lambda value: (-value.evidence_score, value.item.title.casefold())))


def _facts(evidence: tuple[str, ...]) -> Iterable[EvidenceFact]:
    for raw in evidence:
        value = raw.strip()
        lower = value.casefold()
        if lower.startswith("official-status:"):
            yield EvidenceFact("Brreg", "official_status", value.split(":", 1)[1], 30.0)
        elif lower.startswith("organisation-number:"):
            yield EvidenceFact("Brreg", "organisation_number", value.split(":", 1)[1], 12.0)
        elif lower.startswith("municipality:"):
            yield EvidenceFact("Brreg", "municipality", value.split(":", 1)[1], 8.0)
        elif lower.startswith("market-price:"):
            yield EvidenceFact("Market", "market_price", value.split(":", 1)[1], 25.0)
        elif lower.startswith("asset-listing:"):
            yield EvidenceFact("Listing", "asset_listing", value.split(":", 1)[1], 20.0)
        elif lower.startswith("financials:"):
            yield EvidenceFact("Financial", "financials", value.split(":", 1)[1], 20.0)
        elif value.startswith("https://"):
            yield EvidenceFact("Brreg", "official_url", value, 5.0)
