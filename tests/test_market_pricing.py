from opportunity_engine.ods.market_pricing import (
    MarketComparable,
    MarketPriceComparisonEngine,
)
from opportunity_engine.ods.unified_opportunity import UnifiedOpportunity


def _opportunity() -> UnifiedOpportunity:
    return UnifiedOpportunity(
        opportunity_id="unified-auksjonen-123",
        source_name="Auksjonen.no",
        source_document_id="auksjonen-123",
        title="Butikkinnredning",
        url="https://example.test/123",
        description="Komplett butikkinnredning",
        current_price_nok=5000,
        city="Trondheim",
        ends_at=None,
        fee_text=None,
        mva_status="unknown",
        image_urls=(),
        missing_fields=("ends_at", "fee_text", "mva_status"),
        raw_metadata={},
    )


def _comp(identifier: str, price: float, relevance: float = 1.0) -> MarketComparable:
    return MarketComparable(identifier, f"Comparable {identifier}", price, "verified", relevance=relevance)


def test_builds_conservative_market_report() -> None:
    report = MarketPriceComparisonEngine().compare(
        _opportunity(),
        (_comp("a", 8000), _comp("b", 10000), _comp("c", 12000)),
    )

    assert report.comparable_count == 3
    assert report.low_price_nok == 8000
    assert report.median_price_nok == 10000
    assert report.high_price_nok == 12000
    assert report.conservative_resale_nok == 8500
    assert report.confidence == "medium"


def test_missing_comparables_do_not_invent_value() -> None:
    report = MarketPriceComparisonEngine().compare(_opportunity(), ())

    assert report.conservative_resale_nok is None
    assert report.confidence == "insufficient"
    assert report.warnings


def test_duplicate_comparables_are_ignored() -> None:
    report = MarketPriceComparisonEngine().compare(
        _opportunity(),
        (_comp("a", 8000), _comp("a", 20000), _comp("b", 10000)),
    )

    assert report.comparable_count == 2
    assert report.comparable_ids == ("a", "b")
    assert report.confidence == "low"


def test_wide_price_spread_reduces_confidence() -> None:
    report = MarketPriceComparisonEngine().compare(
        _opportunity(),
        tuple(_comp(str(index), price) for index, price in enumerate((1000, 2000, 3000, 4000, 5000, 6000))),
    )

    assert report.confidence == "medium"
    assert "wide spread" in report.warnings[0].lower()


def test_invalid_comparable_is_rejected() -> None:
    try:
        _comp("bad", 0)
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("expected ValueError")
