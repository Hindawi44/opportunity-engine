from __future__ import annotations

from datetime import datetime, timezone

import pytest

from opportunity_engine.discovery.keyword_discovery_lab import (
    KeywordCandidate,
    _term_present,
    run_keyword_discovery_lab,
    score_keyword,
)
from opportunity_engine.discovery.search_provider import SearchHit


class FakeProvider:
    name = "fake"

    def __init__(self, hits_by_query):
        self.hits_by_query = hits_by_query
        self.calls = []

    def search(self, query: str, *, count: int = 10):
        self.calls.append((query, count))
        return self.hits_by_query.get(query, [])[:count]


def _strong_hit(rank: int = 1) -> SearchHit:
    return SearchHit(
        title="Stock abbigliamento ingrosso - liquidazione magazzino Milano",
        url=f"https://grossista{rank}.it/stock",
        description=(
            "Azienda Srl vende lotti e rimanenze di magazzino. "
            "Prezzi per pezzi disponibili, pronta consegna B2B."
        ),
        provider="Fake Search",
    )


def test_strong_b2b_liquidation_keyword_is_promoted():
    candidate = KeywordCandidate("it-test", "TEST", "stock abbigliamento ingrosso")
    result = score_keyword(candidate, [_strong_hit(1), _strong_hit(2)])

    assert result["decision"] == "PROMOTE"
    assert result["score"] >= 80
    assert result["metrics"]["actionable_yield"] == 1.0
    assert result["metrics"]["false_positive_ratio"] == 0.0


def test_consumer_marketplace_result_is_rejected():
    candidate = KeywordCandidate("it-retail", "TEST", "stock abbigliamento")
    hit = SearchHit(
        title="Stock abbigliamento - acquista online",
        url="https://www.amazon.it/example",
        description="Shop online, carrello e spedizione gratuita.",
        provider="Fake Search",
    )
    result = score_keyword(candidate, [hit])

    assert result["decision"] == "REJECT"
    assert result["metrics"]["false_positive_ratio"] == 1.0
    assert result["metrics"]["actionable_yield"] == 0.0


def test_term_matching_does_not_use_substrings():
    assert _term_present("vasta selezione moda", "asta") is False
    assert _term_present("asta abbigliamento", "asta") is True
    assert _term_present("modalità di vendita", "moda") is False
    assert _term_present("moda italiana", "moda") is True


def test_lab_is_bounded_and_does_not_enable_production_writes():
    candidates = (
        KeywordCandidate("one", "TEST", "query one"),
        KeywordCandidate("two", "TEST", "query two"),
    )
    provider = FakeProvider({"query one": [_strong_hit()]})

    report = run_keyword_discovery_lab(
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, key, freshness: provider,
        candidates=candidates,
        keyword_limit=1,
        results_per_keyword=1,
        observed_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
    )

    assert report["status"] == "SUCCESS"
    assert report["queries_attempted"] == 1
    assert report["queries_succeeded"] == 1
    assert provider.calls == [("query one", 1)]
    assert report["production_write_enabled"] is False
    assert report["promotion_to_live_engine_enabled"] is False
    assert report["automatic_contact"] is False
    assert report["automatic_purchase"] is False


def test_missing_api_key_blocks_before_search():
    report = run_keyword_discovery_lab(environment={})
    assert report["status"] == "BLOCKED_CONFIGURATION"
    assert report["block_reason"] == "BRAVE_SEARCH_API_KEY_MISSING"


def test_result_limit_above_safety_ceiling_is_rejected():
    with pytest.raises(ValueError):
        run_keyword_discovery_lab(
            environment={"BRAVE_SEARCH_API_KEY": "test-key"},
            results_per_keyword=11,
        )
