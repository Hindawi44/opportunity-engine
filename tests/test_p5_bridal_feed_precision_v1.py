from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.discovery.bridal_english_market_search import (
    ENGLISH_BRIDAL_QUERIES,
    english_bridal_signal_from_hit,
)
from opportunity_engine.discovery.bridal_liquidation_feed import (
    BRIDAL_QUERIES,
    bridal_signal_from_hit,
)
from opportunity_engine.discovery.bridal_term_boundary_cleanup import (
    PATCH_SCHEMA_VERSION,
    boundary_aware_matched_terms,
)
from opportunity_engine.discovery.search_provider import SearchHit


NOW = datetime(2026, 8, 16, 21, 0, tzinfo=timezone.utc)


def test_boundary_matcher_rejects_embedded_words_but_keeps_real_terms() -> None:
    assert boundary_aware_matched_terms("Stockholm", ("stock",)) == []
    assert boundary_aware_matched_terms("Lagerström", ("lager",)) == []
    assert boundary_aware_matched_terms("stock clearance!", ("stock", "stock clearance")) == [
        "stock",
        "stock clearance",
    ]
    assert boundary_aware_matched_terms("lager säljes", ("lager",)) == ["lager"]
    assert PATCH_SCHEMA_VERSION == "bridal-term-boundary-cleanup-1.0"


def test_swedish_name_containing_lager_does_not_fake_commercial_batch_evidence() -> None:
    signal = bridal_signal_from_hit(
        SearchHit(
            title="Brudklänning från konkurs hos Lagerström",
            url="https://example.se/lagerstrom-news",
            description="Artikel om en enskild klänning och designern.",
            provider="Brave Search",
        ),
        market_code="SE",
        query=BRIDAL_QUERIES["SE"],
        observed_at=NOW,
    )

    assert signal is None


def test_stock_inside_stockholm_does_not_fake_english_inventory_evidence() -> None:
    signal = english_bridal_signal_from_hit(
        SearchHit(
            title="Wedding dress designer bankruptcy in Stockholm",
            url="https://example.se/stockholm-profile",
            description="Profile of one dress designer; no inventory sale is described.",
            provider="Brave Search",
        ),
        market_code="SE",
        query=ENGLISH_BRIDAL_QUERIES["SE"],
        observed_at=NOW,
    )

    assert signal is None


def test_valid_english_bridal_stock_clearance_still_passes() -> None:
    signal = english_bridal_signal_from_hit(
        SearchHit(
            title="Bridal boutique closing down – wedding dress stock clearance",
            url="https://example.no/bridal-closeout",
            description="Full bridal inventory and sample wedding dresses offered for sale.",
            provider="Brave Search",
        ),
        market_code="NO",
        query=ENGLISH_BRIDAL_QUERIES["NO"],
        observed_at=NOW,
    )

    assert signal is not None
    assert signal.signal_type.value == "BUSINESS_CLOSURE"
    assert "stock clearance" in signal.metadata["event_terms"]
    assert signal.metadata["commercial_batch_gate"] is True


def test_valid_german_bridal_liquidation_compounds_still_pass() -> None:
    signal = bridal_signal_from_hit(
        SearchHit(
            title="Brautmodengeschäft Insolvenz – Brautkleider Restposten",
            url="https://example.de/braut-restposten",
            description="Warenbestand und Musterkleider werden im Lagerverkauf angeboten.",
            provider="Brave Search",
        ),
        market_code="DE",
        query=BRIDAL_QUERIES["DE"],
        observed_at=NOW,
    )

    assert signal is not None
    assert signal.signal_type.value == "INSOLVENCY_OR_LIQUIDATION"
    assert signal.metadata["commercial_batch_gate"] is True
