from datetime import datetime, timezone

import pytest

from opportunity_engine.external_market_comparables import (
    ComparableCandidate,
    MarketComparablesEngine,
    MarketConfidence,
)


NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


def candidate(url: str, price: float | None, similarity: float, observed_at: str = "2026-07-20T00:00:00+00:00"):
    return ComparableCandidate(
        title="Butikkinnredning",
        url=url,
        price_nok=price,
        source_name="source",
        observed_at=observed_at,
        similarity_score=similarity,
    )


def test_rejects_missing_price_low_similarity_old_and_duplicate():
    engine = MarketComparablesEngine(minimum_accepted=2)
    result = engine.analyse(
        [
            candidate("https://a.no/1", 1000, 0.9),
            candidate("https://a.no/1/", 1100, 0.9),
            candidate("https://b.no/2", None, 0.9),
            candidate("https://c.no/3", 1200, 0.2),
            candidate("https://d.no/4", 1300, 0.9, "2024-01-01T00:00:00+00:00"),
        ],
        now=NOW,
    )
    assert len(result.accepted) == 1
    reasons = {reason for item in result.rejected for reason in item.reasons}
    assert {"duplicate_url", "missing_explicit_price", "similarity_below_threshold", "too_old"} <= reasons
    assert result.conservative_market_value_nok is None
    assert result.confidence is MarketConfidence.INSUFFICIENT


def test_computes_low_median_range_and_conservative_percentile():
    engine = MarketComparablesEngine(minimum_accepted=3)
    result = engine.analyse(
        [
            candidate("https://a.no/1", 1000, 0.9),
            candidate("https://b.no/2", 2000, 0.85),
            candidate("https://c.no/3", 3000, 0.8),
            candidate("https://d.no/4", 4000, 0.75),
        ],
        now=NOW,
    )
    assert result.lowest_reliable_price_nok == 1000
    assert result.median_price_nok == 2500
    assert result.price_range_nok == (1000, 4000)
    assert result.conservative_market_value_nok == 1750
    assert result.confidence is MarketConfidence.MEDIUM


def test_high_confidence_requires_volume_similarity_and_independent_domains():
    engine = MarketComparablesEngine(minimum_accepted=3)
    result = engine.analyse(
        [candidate(f"https://{domain}/{index}", 1000 + index * 100, 0.9)
         for index, domain in enumerate(("a.no", "b.no", "c.no", "a.no", "b.no", "c.no"), start=1)],
        now=NOW,
    )
    assert result.confidence is MarketConfidence.HIGH


def test_invalid_candidate_values_are_rejected_early():
    with pytest.raises(ValueError):
        candidate("http://a.no/1", 1000, 0.9)
    with pytest.raises(ValueError):
        candidate("https://a.no/1", -1, 0.9)
    with pytest.raises(ValueError):
        candidate("https://a.no/1", 1, 1.1)
