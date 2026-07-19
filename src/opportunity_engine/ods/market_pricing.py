"""Conservative market-price comparison for unified opportunities."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Iterable

from .unified_opportunity import UnifiedOpportunity


@dataclass(frozen=True)
class MarketComparable:
    """One verified comparable listing or completed sale."""

    comparable_id: str
    title: str
    price_nok: float
    source_name: str
    url: str | None = None
    city: str | None = None
    condition: str | None = None
    relevance: float = 1.0

    def __post_init__(self) -> None:
        if not self.comparable_id.strip() or not self.title.strip() or not self.source_name.strip():
            raise ValueError("comparable id, title, and source are required")
        if self.price_nok <= 0:
            raise ValueError("comparable price must be positive")
        if not 0.0 < self.relevance <= 1.0:
            raise ValueError("relevance must be between 0 and 1")


@dataclass(frozen=True)
class MarketPriceReport:
    """Auditable conservative resale estimate."""

    opportunity_id: str
    comparable_count: int
    low_price_nok: float | None
    median_price_nok: float | None
    high_price_nok: float | None
    conservative_resale_nok: float | None
    confidence: str
    comparable_ids: tuple[str, ...]
    warnings: tuple[str, ...]


class MarketPriceComparisonEngine:
    """Estimate resale value from supplied verified comparables only."""

    def compare(
        self,
        opportunity: UnifiedOpportunity,
        comparables: Iterable[MarketComparable],
    ) -> MarketPriceReport:
        usable = self._deduplicate(comparables)
        warnings: list[str] = []
        if not usable:
            return MarketPriceReport(
                opportunity_id=opportunity.opportunity_id,
                comparable_count=0,
                low_price_nok=None,
                median_price_nok=None,
                high_price_nok=None,
                conservative_resale_nok=None,
                confidence="insufficient",
                comparable_ids=(),
                warnings=("No verified market comparables were supplied.",),
            )

        prices = sorted(item.price_nok for item in usable)
        weighted = sorted(item.price_nok * item.relevance for item in usable)
        low = prices[0]
        mid = float(median(prices))
        high = prices[-1]
        conservative = min(mid * 0.85, float(median(weighted)))

        if len(usable) < 3:
            confidence = "low"
            warnings.append("Fewer than three comparables; estimate is provisional.")
        elif len(usable) < 6:
            confidence = "medium"
        else:
            confidence = "high"

        if high / low >= 2.5:
            warnings.append("Comparable prices have a wide spread.")
            if confidence == "high":
                confidence = "medium"
            elif confidence == "medium":
                confidence = "low"

        return MarketPriceReport(
            opportunity_id=opportunity.opportunity_id,
            comparable_count=len(usable),
            low_price_nok=round(low, 2),
            median_price_nok=round(mid, 2),
            high_price_nok=round(high, 2),
            conservative_resale_nok=round(conservative, 2),
            confidence=confidence,
            comparable_ids=tuple(item.comparable_id for item in usable),
            warnings=tuple(warnings),
        )

    @staticmethod
    def _deduplicate(comparables: Iterable[MarketComparable]) -> tuple[MarketComparable, ...]:
        by_id: dict[str, MarketComparable] = {}
        for item in comparables:
            by_id.setdefault(item.comparable_id, item)
        return tuple(by_id.values())
