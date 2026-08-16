from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.discovery import bridal_liquidation_feed as bridal_feed
from opportunity_engine.discovery.bridal_event_purity_cleanup import PATCH_SCHEMA_VERSION
from opportunity_engine.discovery.bridal_liquidation_feed import (
    BRIDAL_QUERY_PACKS,
    BRIDAL_QUERIES,
    bridal_signal_from_hit,
)
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.market_intelligence import MarketSignalType


NOW = datetime(2026, 8, 16, 18, 26, tzinfo=timezone.utc)


def test_swedish_sample_dresses_without_sale_event_are_rejected() -> None:
    signal = bridal_signal_from_hit(
        SearchHit(
            title="Brudklänningar och provklänningar i showroom",
            url="https://example.se/showroom",
            description="Brudbutik med provklänningar och butiksexemplar för provning.",
            provider="Brave Search",
        ),
        market_code="SE",
        query=BRIDAL_QUERY_PACKS["SE"][1],
        observed_at=NOW,
    )

    assert signal is None


def test_german_editorial_sample_dress_mention_without_event_is_rejected() -> None:
    """Mirrors the weak Run #178 advice-page pattern: inventory noun != market event."""
    signal = bridal_signal_from_hit(
        SearchHit(
            title="Brautkleider günstig kaufen – praktische Spartipps",
            url="https://example.de/ratgeber-brautkleider",
            description=(
                "Ein Ratgeber erklärt, dass Ausstellungsstücke bei verschiedenen Anbietern "
                "verkauft werden können."
            ),
            provider="Brave Search",
        ),
        market_code="DE",
        query=BRIDAL_QUERY_PACKS["DE"][1],
        observed_at=NOW,
    )

    assert signal is None


def test_swedish_real_stock_sale_still_passes() -> None:
    signal = bridal_signal_from_hit(
        SearchHit(
            title="Lagerförsäljning av brudklänningar och provklänningar",
            url="https://example.se/brud-lagerforsaljning",
            description="Brudbutik säljer provklänningar från lagret i en lagerförsäljning.",
            provider="Brave Search",
        ),
        market_code="SE",
        query=BRIDAL_QUERY_PACKS["SE"][1],
        observed_at=NOW,
    )

    assert signal is not None
    assert signal.signal_type is MarketSignalType.WAREHOUSE_SURPLUS
    assert "lagerförsäljning" in signal.metadata["event_terms"]
    assert "provklänningar" in signal.metadata["commercial_batch_terms"]


def test_german_real_bridal_sample_sale_still_passes() -> None:
    signal = bridal_signal_from_hit(
        SearchHit(
            title="Brautkleider Musterverkauf",
            url="https://example.de/braut-musterverkauf",
            description="Brautmodegeschäft verkauft Musterkleider im Musterverkauf.",
            provider="Brave Search",
        ),
        market_code="DE",
        query=BRIDAL_QUERY_PACKS["DE"][1],
        observed_at=NOW,
    )

    assert signal is not None
    assert signal.signal_type is MarketSignalType.WAREHOUSE_SURPLUS
    assert "musterverkauf" in signal.metadata["event_terms"]
    assert "musterkleider" in signal.metadata["commercial_batch_terms"]


def test_norwegian_real_clearance_still_passes() -> None:
    signal = bridal_signal_from_hit(
        SearchHit(
            title="Lagertømming av brudekjoler og prøvekjoler",
            url="https://example.no/brude-lagertomming",
            description="Brudebutikk gjennomfører lagertømming av prøvekjoler.",
            provider="Brave Search",
        ),
        market_code="NO",
        query=BRIDAL_QUERIES["NO"],
        observed_at=NOW,
    )

    assert signal is not None
    assert signal.signal_type is MarketSignalType.WAREHOUSE_SURPLUS
    assert "lagertømming" in signal.metadata["event_terms"]


def test_inventory_nouns_are_not_surplus_event_terms_anymore() -> None:
    assert "prøvekjoler" not in bridal_feed._SURPLUS_TERMS["NO"]
    assert "provklänningar" not in bridal_feed._SURPLUS_TERMS["SE"]
    assert "butiksexemplar" not in bridal_feed._SURPLUS_TERMS["SE"]
    assert "musterkleider" not in bridal_feed._SURPLUS_TERMS["DE"]
    assert "ausstellungsstücke" not in bridal_feed._SURPLUS_TERMS["DE"]

    assert "prøvekjoler" in bridal_feed._COMMERCIAL_BATCH_TERMS["NO"]
    assert "provklänningar" in bridal_feed._COMMERCIAL_BATCH_TERMS["SE"]
    assert "musterkleider" in bridal_feed._COMMERCIAL_BATCH_TERMS["DE"]

    assert bridal_feed.BRIDAL_EVENT_PURITY_PATCH_SCHEMA_VERSION == PATCH_SCHEMA_VERSION
    assert PATCH_SCHEMA_VERSION == "bridal-event-purity-cleanup-1.1"
