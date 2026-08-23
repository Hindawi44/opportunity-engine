from __future__ import annotations

import pytest

from opportunity_engine.discovery.exa_exact_lot_shadow_hunt import MARKET_EXACT_LOT_QUERIES
from scripts.run_exa_brave_shadow_benchmark import (
    MARKET_QUERIES,
    market_queries_for_mode,
)


def test_discovery_mode_preserves_existing_clothing_queries() -> None:
    assert market_queries_for_mode("discovery") == MARKET_QUERIES


def test_exact_lot_mode_reuses_authoritative_exact_lot_queries() -> None:
    selected = market_queries_for_mode("exact_lot")

    assert selected == MARKET_EXACT_LOT_QUERIES
    assert selected is not MARKET_EXACT_LOT_QUERIES
    assert set(selected) == {"NO", "SE", "DE", "FR", "IT", "NL"}


def test_exact_lot_mode_contains_commercial_specificity_intent_in_every_market() -> None:
    selected = market_queries_for_mode("exact_lot")
    required_markers = {
        "NO": ("pris", "stk"),
        "SE": ("pris", "st"),
        "DE": ("preis", "stück"),
        "FR": ("prix", "quantité"),
        "IT": ("prezzo", "pezzi"),
        "NL": ("prijs", "stuks"),
    }

    for market, query in selected.items():
        folded = query.casefold()
        assert all(marker in folded for marker in required_markers[market])


def test_unknown_query_mode_fails_closed() -> None:
    with pytest.raises(ValueError, match="query_mode"):
        market_queries_for_mode("general_merchandise")
