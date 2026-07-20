from opportunity_engine.ods.live_data import SourceDocument
from opportunity_engine.ods.market_pricing import MarketComparable, MarketPriceComparisonEngine
from opportunity_engine.ods.market_verification import MarketPriceVerificationEngine
from opportunity_engine.ods.unified_opportunity import UnifiedOpportunityExtractor


def _opportunity(price: float | None = 10_000):
    document = SourceDocument(
        document_id="market-1",
        source_name="Auksjonen.no",
        source_type="public_auction_listing",
        title="Butikkinnredning",
        text="Butikkinnredning",
        url="https://example.test/items/1",
        country="Norway",
        metadata={"current_price_nok": price, "mva_status": "included"},
    )
    return UnifiedOpportunityExtractor().extract((document,))[0]


def _market(opportunity, prices):
    comparables = tuple(
        MarketComparable(
            comparable_id=f"c{index}",
            title="Comparable",
            price_nok=price,
            source_name="verified",
        )
        for index, price in enumerate(prices, start=1)
    )
    return MarketPriceComparisonEngine().compare(opportunity, comparables)


def test_strong_discount_is_verified() -> None:
    opportunity = _opportunity(10_000)
    market = _market(opportunity, (20_000, 22_000, 24_000))

    result = MarketPriceVerificationEngine().verify(opportunity, market)

    assert result.status == "strong_discount"
    assert result.is_verified is True
    assert result.discount_vs_conservative is not None
    assert result.discount_vs_conservative >= 0.30
    assert result.comparable_count == 3


def test_price_above_market_is_rejected_by_verification_label() -> None:
    opportunity = _opportunity(30_000)
    market = _market(opportunity, (20_000, 22_000, 24_000))

    result = MarketPriceVerificationEngine().verify(opportunity, market)

    assert result.status == "overpriced"
    assert result.is_verified is True
    assert result.discount_vs_conservative is not None
    assert result.discount_vs_conservative < 0
    assert result.warnings


def test_missing_comparables_never_create_market_value() -> None:
    opportunity = _opportunity(10_000)
    market = _market(opportunity, ())

    result = MarketPriceVerificationEngine().verify(opportunity, market)

    assert result.status == "unavailable"
    assert result.conservative_market_value_nok is None
    assert result.discount_vs_conservative is None
    assert result.is_verified is False


def test_fewer_than_three_comparables_requires_manual_review() -> None:
    opportunity = _opportunity(10_000)
    market = _market(opportunity, (20_000, 22_000))

    result = MarketPriceVerificationEngine().verify(opportunity, market)

    assert result.status == "needs_review"
    assert result.is_verified is False
