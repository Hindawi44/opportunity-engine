from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.discovery import bridal_liquidation_feed as bridal_feed
from opportunity_engine.discovery.bridal_event_purity_cleanup import PATCH_SCHEMA_VERSION
from opportunity_engine.discovery.bridal_liquidation_feed import (
    BRIDAL_QUERY_PACKS,
    bridal_signal_from_hit,
)
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.market_intelligence import MarketSignalType


NOW = datetime(2026, 8, 16, 18, 26, tzinfo=timezone.utc)


def test_run178_avinia_bridal_outlet_remains_a_valid_surplus_signal() -> None:
    """Real Run #178 positive control: precision cleanup must not erase true outlet stock."""
    signal = bridal_signal_from_hit(
        SearchHit(
            title="Outlet - AVINIA",
            url="https://www.avinia.de/outlet",
            description=(
                "Denn hier erwarten Dich Musterkleider, Einzelstücke und Modelle aus "
                "vergangenen Kollektionen – zu Preisen, die auch kleinen Budgets gerecht "
                "werden. Im Brautkleid-Outlet bieten wir verschiedene Brautkleid-Stile."
            ),
            provider="Brave Search",
        ),
        market_code="DE",
        query=BRIDAL_QUERY_PACKS["DE"][1],
        observed_at=NOW,
    )

    assert signal is not None
    assert signal.signal_type is MarketSignalType.WAREHOUSE_SURPLUS
    assert "outlet" in signal.metadata["event_terms"]
    assert "musterkleider" in signal.metadata["commercial_batch_terms"]


def test_german_advice_page_with_sample_pieces_still_rejects_without_outlet_event() -> None:
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


def test_outlet_is_an_explicit_german_surplus_context_not_a_batch_shortcut() -> None:
    assert "outlet" in bridal_feed._SURPLUS_TERMS["DE"]
    assert "musterkleider" not in bridal_feed._SURPLUS_TERMS["DE"]
    assert "ausstellungsstücke" not in bridal_feed._SURPLUS_TERMS["DE"]
    assert "musterkleider" in bridal_feed._COMMERCIAL_BATCH_TERMS["DE"]
    assert bridal_feed.BRIDAL_EVENT_PURITY_PATCH_SCHEMA_VERSION == PATCH_SCHEMA_VERSION
    assert PATCH_SCHEMA_VERSION == "bridal-event-purity-cleanup-1.1"
