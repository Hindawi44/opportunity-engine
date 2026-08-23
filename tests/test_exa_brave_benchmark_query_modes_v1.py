from __future__ import annotations

import pytest

from opportunity_engine.discovery.exa_exact_lot_shadow_hunt import MARKET_EXACT_LOT_QUERIES
import scripts.run_exa_brave_shadow_benchmark as benchmark
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


def test_exact_lot_mode_drives_both_providers_with_identical_queries(monkeypatch) -> None:
    calls: dict[str, list[str]] = {"exa": [], "brave": []}

    class FakeExaSearchProvider:
        def __init__(self, api_key: str) -> None:
            assert api_key == "exa-test-key"

        def search(self, query: str, *, count: int):
            assert count == 2
            calls["exa"].append(query)
            return []

    class FakeBraveSearchProvider:
        def __init__(self, api_key: str, **kwargs) -> None:
            assert api_key == "brave-test-key"

        def search(self, query: str, *, count: int):
            assert count == 2
            calls["brave"].append(query)
            return []

    monkeypatch.setattr(benchmark, "ExaSearchProvider", FakeExaSearchProvider)
    monkeypatch.setattr(benchmark, "BraveSearchProvider", FakeBraveSearchProvider)

    report = benchmark.run_benchmark(
        exa_api_key="exa-test-key",
        brave_api_key="brave-test-key",
        markets=["NO", "DE"],
        results_per_query=2,
        provider_mode="both",
        query_mode="exact_lot",
    )

    expected = [MARKET_EXACT_LOT_QUERIES["NO"], MARKET_EXACT_LOT_QUERIES["DE"]]
    assert calls["exa"] == expected
    assert calls["brave"] == expected
    assert report["query_mode"] == "exact_lot"
    assert report["query_set"] == {
        "NO": MARKET_EXACT_LOT_QUERIES["NO"],
        "DE": MARKET_EXACT_LOT_QUERIES["DE"],
    }


def test_unknown_query_mode_fails_closed() -> None:
    with pytest.raises(ValueError, match="query_mode"):
        market_queries_for_mode("general_merchandise")
