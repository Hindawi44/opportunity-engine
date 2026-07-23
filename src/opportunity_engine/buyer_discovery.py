"""Evidence-aware buyer discovery for Opportunity Engine v2.6.3.

The engine ranks explicit buyer candidates. It never contacts candidates, invents
contact details, or treats a search result as confirmed buying intent.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Iterable
from urllib.parse import urlparse


class BuyerType(str, Enum):
    SPECIALIST_DEALER = "specialist_dealer"
    WHOLESALER = "wholesaler"
    LIQUIDATION_COMPANY = "liquidation_company"
    END_USER_BUSINESS = "end_user_business"
    BROKER = "broker"
    LOCAL_BUYER = "local_buyer"
    OTHER = "other"


class BuyerConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class BuyerCandidate:
    name: str
    website_url: str
    buyer_type: BuyerType
    source_url: str
    source_name: str
    rationale: str
    location: str | None = None
    contact_url: str | None = None
    email: str | None = None
    phone: str | None = None
    matched_terms: tuple[str, ...] = ()
    scenario_ids: tuple[str, ...] = ()
    evidence_score: float | None = None

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.rationale.strip():
            raise ValueError("name and rationale are required")
        for value, field_name in ((self.website_url, "website_url"), (self.source_url, "source_url")):
            if not _is_https(value):
                raise ValueError(f"{field_name} must use HTTPS")
        if self.contact_url is not None and not _is_https(self.contact_url):
            raise ValueError("contact_url must use HTTPS")
        if self.evidence_score is not None and not 0 <= self.evidence_score <= 100:
            raise ValueError("evidence_score must be between 0 and 100")

    @property
    def candidate_id(self) -> str:
        key = f"{_domain(self.website_url)}|{self.name.casefold().strip()}"
        return "buyer_" + sha256(key.encode("utf-8")).hexdigest()[:20]


@dataclass(frozen=True, slots=True)
class RankedBuyer:
    candidate: BuyerCandidate
    fit_score: float
    confidence: BuyerConfidence
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BuyerDiscoveryResult:
    accepted: tuple[RankedBuyer, ...]
    rejected: tuple[tuple[str, str], ...]
    duplicate_count: int


class BuyerDiscoveryEngine:
    """Filter and rank explicit buyer candidates for one opportunity."""

    def discover(
        self,
        candidates: Iterable[BuyerCandidate],
        *,
        opportunity_terms: Iterable[str],
        opportunity_location: str | None = None,
        required_scenario_ids: Iterable[str] = (),
        minimum_fit_score: float = 45.0,
    ) -> BuyerDiscoveryResult:
        terms = {item.casefold().strip() for item in opportunity_terms if item.strip()}
        required_scenarios = {item.strip() for item in required_scenario_ids if item.strip()}
        accepted: list[RankedBuyer] = []
        rejected: list[tuple[str, str]] = []
        seen_domains: set[str] = set()
        duplicates = 0

        for candidate in candidates:
            domain = _domain(candidate.website_url)
            if domain in seen_domains:
                duplicates += 1
                rejected.append((candidate.candidate_id, "duplicate_domain"))
                continue
            seen_domains.add(domain)

            score, reasons, warnings = self._score(
                candidate,
                terms=terms,
                opportunity_location=opportunity_location,
                required_scenarios=required_scenarios,
            )
            if score < minimum_fit_score:
                rejected.append((candidate.candidate_id, "fit_below_threshold"))
                continue
            accepted.append(
                RankedBuyer(
                    candidate=candidate,
                    fit_score=score,
                    confidence=self._confidence(score),
                    reasons=tuple(reasons),
                    warnings=tuple(warnings),
                )
            )

        accepted.sort(key=lambda item: (-item.fit_score, item.candidate.name.casefold()))
        return BuyerDiscoveryResult(tuple(accepted), tuple(rejected), duplicates)

    @staticmethod
    def _score(
        candidate: BuyerCandidate,
        *,
        terms: set[str],
        opportunity_location: str | None,
        required_scenarios: set[str],
    ) -> tuple[float, list[str], list[str]]:
        score = 0.0
        reasons: list[str] = []
        warnings: list[str] = []

        matched = {item.casefold().strip() for item in candidate.matched_terms if item.strip()}
        overlap = terms.intersection(matched)
        if terms:
            relevance = len(overlap) / len(terms)
            score += min(40.0, relevance * 40.0)
            reasons.append(f"Matched {len(overlap)} of {len(terms)} opportunity terms")
        else:
            warnings.append("No opportunity terms supplied")

        type_points = {
            BuyerType.SPECIALIST_DEALER: 20.0,
            BuyerType.WHOLESALER: 18.0,
            BuyerType.END_USER_BUSINESS: 16.0,
            BuyerType.LIQUIDATION_COMPANY: 14.0,
            BuyerType.BROKER: 12.0,
            BuyerType.LOCAL_BUYER: 10.0,
            BuyerType.OTHER: 5.0,
        }[candidate.buyer_type]
        score += type_points
        reasons.append(f"Buyer type: {candidate.buyer_type.value}")

        candidate_scenarios = set(candidate.scenario_ids)
        if required_scenarios:
            scenario_overlap = required_scenarios.intersection(candidate_scenarios)
            if scenario_overlap:
                score += min(15.0, 7.5 * len(scenario_overlap))
                reasons.append("Linked to relevant scenario")
            else:
                warnings.append("No relevant scenario link")
        elif candidate_scenarios:
            score += 5.0

        if opportunity_location and candidate.location:
            if opportunity_location.casefold() in candidate.location.casefold() or candidate.location.casefold() in opportunity_location.casefold():
                score += 10.0
                reasons.append("Location match")
            else:
                score += 3.0
                warnings.append("Buyer is outside the opportunity location")

        if candidate.contact_url or candidate.email or candidate.phone:
            score += 5.0
            reasons.append("Public contact channel is available")
        else:
            warnings.append("No public contact channel supplied")

        if candidate.evidence_score is not None:
            score += min(10.0, candidate.evidence_score / 10.0)
            reasons.append(f"Evidence strength: {candidate.evidence_score:.1f}/100")
        else:
            warnings.append("Evidence score is missing")

        return round(min(100.0, score), 2), reasons, warnings

    @staticmethod
    def _confidence(score: float) -> BuyerConfidence:
        if score >= 75:
            return BuyerConfidence.HIGH
        if score >= 55:
            return BuyerConfidence.MEDIUM
        return BuyerConfidence.LOW


def _domain(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def _is_https(url: str) -> bool:
    return bool(url) and urlparse(url).scheme == "https" and bool(urlparse(url).hostname)
