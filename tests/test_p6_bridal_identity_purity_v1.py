from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.discovery import bridal_liquidation_feed as bridal_feed
from opportunity_engine.discovery.bridal_identity_purity_cleanup import PATCH_SCHEMA_VERSION
from opportunity_engine.discovery.bridal_liquidation_feed import (
    BRIDAL_QUERY_PACKS,
    bridal_signal_from_hit,
)
from opportunity_engine.discovery.search_provider import SearchHit


NOW = datetime(2026, 8, 16, 18, 26, tzinfo=timezone.utc)


def test_run178_swedish_sauna_false_positive_is_rejected() -> None:
    """Real Run #178 contamination: generic shop samples must not imply BRIDAL."""
    signal = bridal_signal_from_hit(
        SearchHit(
            title="Fyndhörna bastuprodukter",
            url="https://www.bastuspecialisten.se/blog/bastu-lagerrensning.html",
            description=(
                "Utförsäljning av butiksexemplar, utgångna produkter och lagervaror, "
                "stort som smått. Här samlar vi bastuartiklar som vi säljer bort."
            ),
            provider="Brave Search",
        ),
        market_code="SE",
        query=BRIDAL_QUERY_PACKS["SE"][1],
        observed_at=NOW,
    )

    assert signal is None


def test_swedish_real_bridal_sample_stock_still_passes() -> None:
    signal = bridal_signal_from_hit(
        SearchHit(
            title="Utförsäljning av brudklänningar och butiksexemplar",
            url="https://example.se/brud-sample-sale",
            description=(
                "Brudbutik säljer provklänningar och butiksexemplar för att göra plats "
                "för en ny kollektion."
            ),
            provider="Brave Search",
        ),
        market_code="SE",
        query=BRIDAL_QUERY_PACKS["SE"][1],
        observed_at=NOW,
    )

    assert signal is not None
    assert "brudklänningar" in signal.metadata["bridal_terms"]
    assert "butiksexemplar" not in signal.metadata["bridal_terms"]
    assert "butiksexemplar" in signal.metadata["commercial_batch_terms"]


def test_german_generic_showroom_clearance_is_not_bridal_identity() -> None:
    signal = bridal_signal_from_hit(
        SearchHit(
            title="Ausstellungsstücke im Abverkauf",
            url="https://example.de/moebel-ausstellung",
            description="Möbel-Ausstellungsstücke aus dem Lagerverkauf werden reduziert verkauft.",
            provider="Brave Search",
        ),
        market_code="DE",
        query=BRIDAL_QUERY_PACKS["DE"][1],
        observed_at=NOW,
    )

    assert signal is None


def test_german_real_bridal_sample_sale_still_passes() -> None:
    signal = bridal_signal_from_hit(
        SearchHit(
            title="Brautkleider Musterverkauf – Ausstellungsstücke im Abverkauf",
            url="https://example.de/braut-sample-sale",
            description="Brautmodegeschäft verkauft Musterkleider und Ausstellungsstücke.",
            provider="Brave Search",
        ),
        market_code="DE",
        query=BRIDAL_QUERY_PACKS["DE"][1],
        observed_at=NOW,
    )

    assert signal is not None
    assert "brautkleider" in signal.metadata["bridal_terms"]
    assert "ausstellungsstücke" not in signal.metadata["bridal_terms"]
    assert "ausstellungsstücke" in signal.metadata["commercial_batch_terms"]


def test_generic_sample_words_remain_batch_evidence_only() -> None:
    assert "butiksexemplar" not in bridal_feed._BRIDAL_TERMS["SE"]
    assert "butiksexemplar" in bridal_feed._COMMERCIAL_BATCH_TERMS["SE"]
    assert "ausstellungsstücke" not in bridal_feed._BRIDAL_TERMS["DE"]
    assert "ausstellungsstücke" in bridal_feed._COMMERCIAL_BATCH_TERMS["DE"]
    assert bridal_feed.BRIDAL_IDENTITY_PURITY_PATCH_SCHEMA_VERSION == PATCH_SCHEMA_VERSION
    assert PATCH_SCHEMA_VERSION == "bridal-identity-purity-cleanup-1.0"
