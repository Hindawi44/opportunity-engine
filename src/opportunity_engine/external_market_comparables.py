"""Conservative market-comparables analysis for Opportunity Engine v2.6.2.

The engine accepts explicit candidate comparables, rejects weak or incomplete records,
and computes a conservative value only when enough valid observations exist. Missing
prices remain missing; no values are inferred from search snippets.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from statistics import median
from typing import Iterable
from urllib.parse import urlparse


class ComparableStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class MarketConfidence(str, Enum):
    INSUFFICIENT = "insufficient"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class ComparableCandidate:
    title: str
    url: str
    price_nok: float | None
    source_name: str
    observed_at: str
    similarity_score: float
    condition: str | None = None
    location: str | None = None

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("title cannot be empty")
        if not self.url.startswith("https://"):
            raise ValueError("url must use HTTPS")
        if self.price_nok is not None and self.price_nok < 0:
            raise ValueError("price_nok cannot be negative")
        if not 0 <= self.similarity_score <= 1:
            raise ValueError("similarity_score must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class ComparableDecision:
    candidate: ComparableCandidate
    status: ComparableStatus
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MarketComparablesResult:
    accepted: tuple[ComparableCandidate, ...]
    rejected: tuple[ComparableDecision, ...]
    lowest_reliable_price_nok: float | None
    median_price_nok: float | None
    price_range_nok: tuple[float, float] | None
    conservative_market_value_nok: float | None
    confidence: MarketConfidence
    warnings: tuple[str, ...]


class MarketComparablesEngine:
    """Filter, deduplicate and summarize explicit market comparisons."""

    def __init__(
        self,
        *,
        minimum_similarity: float = 0.65,
        maximum_age_days: int = 365,
        minimum_accepted: int = 3,
        conservative_percentile: float = 0.25,
    ) -> None:
        if not 0 <= minimum_similarity <= 1:
            raise ValueError("minimum_similarity must be between 0 and 1")
        if maximum_age_days <= 0:
            raise ValueError("maximum_age_days must be positive")
        if minimum_accepted <= 0:
            raise ValueError("minimum_accepted must be positive")
        if not 0 <= conservative_percentile <= 1:
            raise ValueError("conservative_percentile must be between 0 and 1")
        self.minimum_similarity = minimum_similarity
        self.maximum_age_days = maximum_age_days
        self.minimum_accepted = minimum_accepted
        self.conservative_percentile = conservative_percentile

    def analyse(
        self,
        candidates: Iterable[ComparableCandidate],
        *,
        now: datetime | None = None,
    ) -> MarketComparablesResult:
        now = now or datetime.now(timezone.utc)
        accepted: list[ComparableCandidate] = []
        rejected: list[ComparableDecision] = []
        seen_urls: set[str] = set()

        for candidate in candidates:
            reasons: list[str] = []
            canonical_url = self._canonical_url(candidate.url)
            if canonical_url in seen_urls:
                reasons.append("duplicate_url")
            if candidate.price_nok is None:
                reasons.append("missing_explicit_price")
            if candidate.similarity_score < self.minimum_similarity:
                reasons.append("similarity_below_threshold")
            age_days = self._age_days(candidate.observed_at, now)
            if age_days is None:
                reasons.append("invalid_observed_at")
            elif age_days > self.maximum_age_days:
                reasons.append("too_old")

            if reasons:
                rejected.append(ComparableDecision(candidate, ComparableStatus.REJECTED, tuple(reasons)))
                continue
            seen_urls.add(canonical_url)
            accepted.append(candidate)

        accepted.sort(key=lambda item: float(item.price_nok or 0))
        prices = [float(item.price_nok) for item in accepted if item.price_nok is not None]
        warnings: list[str] = []
        if len(prices) < self.minimum_accepted:
            warnings.append(
                f"Only {len(prices)} valid comparables; at least {self.minimum_accepted} are required"
            )
            return MarketComparablesResult(
                accepted=tuple(accepted),
                rejected=tuple(rejected),
                lowest_reliable_price_nok=min(prices) if prices else None,
                median_price_nok=median(prices) if prices else None,
                price_range_nok=(min(prices), max(prices)) if prices else None,
                conservative_market_value_nok=None,
                confidence=MarketConfidence.INSUFFICIENT,
                warnings=tuple(warnings),
            )

        conservative = self._percentile(prices, self.conservative_percentile)
        confidence = self._confidence(accepted)
        return MarketComparablesResult(
            accepted=tuple(accepted),
            rejected=tuple(rejected),
            lowest_reliable_price_nok=min(prices),
            median_price_nok=median(prices),
            price_range_nok=(min(prices), max(prices)),
            conservative_market_value_nok=conservative,
            confidence=confidence,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _canonical_url(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}"

    @staticmethod
    def _age_days(value: str, now: datetime) -> int | None:
        try:
            observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        return max(0, (now - observed).days)

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        ordered = sorted(values)
        if len(ordered) == 1:
            return ordered[0]
        index = percentile * (len(ordered) - 1)
        lower = int(index)
        upper = min(lower + 1, len(ordered) - 1)
        fraction = index - lower
        return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 2)

    @staticmethod
    def _confidence(accepted: list[ComparableCandidate]) -> MarketConfidence:
        count = len(accepted)
        average_similarity = sum(item.similarity_score for item in accepted) / count
        independent_domains = {
            (urlparse(item.url).hostname or "").lower().removeprefix("www.") for item in accepted
        }
        if count >= 6 and average_similarity >= 0.8 and len(independent_domains) >= 3:
            return MarketConfidence.HIGH
        if count >= 4 and average_similarity >= 0.72 and len(independent_domains) >= 2:
            return MarketConfidence.MEDIUM
        return MarketConfidence.LOW
