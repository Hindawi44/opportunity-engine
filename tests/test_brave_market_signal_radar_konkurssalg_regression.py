from datetime import datetime, timezone

from opportunity_engine.discovery.brave_market_signal_radar import (
    MARKET_QUERIES,
    market_signal_from_brave_hit,
)
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.market_intelligence import MarketSignalType


def test_norway_radar_keeps_konkurssalg_lagersalg_workwear_signal() -> None:
    hit = SearchHit(
        title="Konkurssalg - 60 % rabatt på arbeidsklær",
        url="https://www.facebook.com/example/posts/123",
        description=(
            "Lagersalg fra konkursbo med stort restlager av arbeidsklær, "
            "vernesko og varer."
        ),
        provider="Brave Search",
    )

    signal = market_signal_from_brave_hit(
        hit,
        market_code="NO",
        query=MARKET_QUERIES["NO"][0],
        rank=1,
        observed_at=datetime(2026, 8, 21, tzinfo=timezone.utc),
    )

    assert signal is not None
    assert signal.signal_type == MarketSignalType.INSOLVENCY_OR_LIQUIDATION
    assert signal.metadata["not_an_opportunity"] is True
    assert "konkurssalg" in signal.metadata["event_terms"]
    assert "arbeidsklær" in signal.metadata["clothing_terms"]


def test_norway_radar_queries_explicitly_cover_konkurssalg_and_lagersalg() -> None:
    combined = " ".join(item.query for item in MARKET_QUERIES["NO"])

    assert "konkurssalg" in combined
    assert "lagersalg" in combined
    assert "vernesko" in combined
