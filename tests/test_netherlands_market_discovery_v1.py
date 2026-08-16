from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from opportunity_engine.discovery.netherlands_market_discovery import (
    DEFAULT_QUERY_BUDGET,
    FEED_FAMILY,
    NETHERLANDS_DISCOVERY_QUERIES,
    collect_netherlands_market_signals,
    netherlands_signal_from_hit,
)
from opportunity_engine.discovery.search_provider import SearchHit


NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)


def _query(intent: str):
    return next(item for item in NETHERLANDS_DISCOVERY_QUERIES if item.intent == intent)


def test_query_pack_covers_core_netherlands_intents() -> None:
    intents = {query.intent for query in NETHERLANDS_DISCOVERY_QUERIES}
    assert DEFAULT_QUERY_BUDGET == 8
    assert intents == {
        "OFFICIAL_PUBLIC_AUCTIONS",
        "OFFICIAL_INSOLVENCY",
        "INSOLVENCY_LIQUIDATION",
        "BUSINESS_CLOSURE",
        "STOCKLOT_WHOLESALE",
        "AUCTION_LOTS",
        "BRIDAL_LIQUIDATION",
        "WAREHOUSE_CLEARANCE",
    }
    assert "veiling.belastingdienst.nl" in NETHERLANDS_DISCOVERY_QUERIES[0].query
    assert "insolventies.rechtspraak.nl" in NETHERLANDS_DISCOVERY_QUERIES[1].query
    assert any("bruidsjurken" in query.query for query in NETHERLANDS_DISCOVERY_QUERIES)
    assert any("handelsvoorraad" in query.query for query in NETHERLANDS_DISCOVERY_QUERIES)


def test_accepts_public_dutch_fashion_insolvency_as_signal_only() -> None:
    signal = netherlands_signal_from_hit(
        SearchHit(
            title="Faillissement kledingwinkel met handelsvoorraad",
            url="https://example.nl/faillissement-mode?utm_source=test",
            description="Curator onderzoekt verkoop van kledingvoorraad en schoenen.",
            provider="Fake Brave",
        ),
        query=_query("INSOLVENCY_LIQUIDATION"),
        rank=1,
        observed_at=NOW,
    )
    assert signal is not None
    assert signal.source_country == "NL"
    assert signal.signal_type.value == "INSOLVENCY_OR_LIQUIDATION"
    assert signal.metadata["feed_family"] == FEED_FAMILY
    assert signal.metadata["inventory_domain"] == "CLOTHING_FASHION"
    assert signal.metadata["source_page_verification_required"] is True
    assert signal.metadata["promotion_to_opportunity_allowed"] is False
    assert signal.metadata["automatic_purchase"] is False
    assert str(signal.source_url) == "https://example.nl/faillissement-mode"


def test_official_queries_require_the_exact_official_domain() -> None:
    tax_query = _query("OFFICIAL_PUBLIC_AUCTIONS")
    accepted = netherlands_signal_from_hit(
        SearchHit(
            title="Handelsvoorraad kleding - veiling",
            url="https://veiling.belastingdienst.nl/handelsvoorraad/kleding-1",
            description="Openbare verkoop van kleding en schoenen per kavel.",
            provider="Fake Brave",
        ),
        query=tax_query,
        rank=1,
        observed_at=NOW,
    )
    rejected = netherlands_signal_from_hit(
        SearchHit(
            title="Handelsvoorraad kleding - veiling",
            url="https://fake-belastingdienst.example/handelsvoorraad/kleding-1",
            description="Openbare verkoop van kleding en schoenen per kavel.",
            provider="Fake Brave",
        ),
        query=tax_query,
        rank=2,
        observed_at=NOW,
    )
    assert accepted is not None
    assert accepted.metadata["source_scope"] == "OFFICIAL_PUBLIC_SOURCE"
    assert rejected is None


def test_bridal_query_requires_explicit_bridal_evidence() -> None:
    query = _query("BRIDAL_LIQUIDATION")
    accepted = netherlands_signal_from_hit(
        SearchHit(
            title="Bruidswinkel failliet - bruidsjurken in voorraad",
            url="https://bridal.example.nl/faillissement",
            description="Bruidsmode en trouwjurken worden via veiling verkocht.",
            provider="Fake Brave",
        ),
        query=query,
        rank=1,
        observed_at=NOW,
    )
    rejected = netherlands_signal_from_hit(
        SearchHit(
            title="Kledingwinkel failliet",
            url="https://news.example.nl/mode-failliet",
            description="Mode en kledingvoorraad na faillissement.",
            provider="Fake Brave",
        ),
        query=query,
        rank=2,
        observed_at=NOW,
    )
    assert accepted is not None
    assert accepted.metadata["inventory_domain"] == "BRIDAL"
    assert rejected is None


def test_stocklot_query_rejects_editorial_inventory_article() -> None:
    signal = netherlands_signal_from_hit(
        SearchHit(
            title="Waarom kledingwinkels veel handelsvoorraad hebben",
            url="https://news.example.nl/voorraad-analyse",
            description="Analyse van restpartijen, winkelvoorraad en textiel in Nederland.",
            provider="Fake Brave",
        ),
        query=_query("STOCKLOT_WHOLESALE"),
        rank=1,
        observed_at=NOW,
    )
    assert signal is None


def test_stocklot_query_keeps_buyer_facing_inventory_offer() -> None:
    signal = netherlands_signal_from_hit(
        SearchHit(
            title="Restpartij kleding te koop - 900 stuks",
            url="https://stock.example.nl/partij-900",
            description="Handelsvoorraad kleding beschikbaar met prijs per partij.",
            provider="Fake Brave",
        ),
        query=_query("STOCKLOT_WHOLESALE"),
        rank=1,
        observed_at=NOW,
    )
    assert signal is not None
    assert "te koop" in signal.metadata["inventory_offer_terms"]
    assert "prijs" in signal.metadata["inventory_offer_terms"]


def test_matching_uses_word_boundaries_not_substrings() -> None:
    signal = netherlands_signal_from_hit(
        SearchHit(
            title="Nieuwe modellencollectie",
            url="https://example.nl/modellen",
            description="Informatie over modellen en textielonderzoek zonder verkoop of voorraad.",
            provider="Fake Brave",
        ),
        query=_query("STOCKLOT_WHOLESALE"),
        rank=1,
        observed_at=NOW,
    )
    assert signal is None


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    @property
    def name(self) -> str:
        return "Fake Brave"

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        self.calls.append((query, count))
        if "site:veiling.belastingdienst.nl" in query:
            return [SearchHit(
                title="Handelsvoorraad kleding - veiling",
                url="https://veiling.belastingdienst.nl/handelsvoorraad/kleding-7",
                description="Openbare verkoop van kleding per kavel.",
                provider="Fake Brave",
            )]
        if "site:insolventies.rechtspraak.nl" in query:
            return [SearchHit(
                title="Faillissement Tulip Mode B.V.",
                url="https://insolventies.rechtspraak.nl/#!/details/7",
                description="Faillissement kledingwinkel; curator vermeld.",
                provider="Fake Brave",
            )]
        if "bruidsjurken" in query:
            return [SearchHit(
                title="Bruidswinkel failliet - bruidsjurken in voorraad",
                url="https://bridal.example.nl/faillissement",
                description="Bruidsmode voorraad via veiling beschikbaar.",
                provider="Fake Brave",
            )]
        return [SearchHit(
            title="Restpartij kleding te koop",
            url="https://stock.example.nl/partij",
            description="Handelsvoorraad kleding beschikbaar met prijs.",
            provider="Fake Brave",
        )]


def test_collection_is_bounded_deduplicated_and_keeps_canonical_coverage_unchanged() -> None:
    provider = FakeProvider()
    report = collect_netherlands_market_signals(
        observed_at=NOW,
        environment={"BRAVE_SEARCH_API_KEY": "secret"},
        provider_factory=lambda market, key, freshness: provider,
        query_budget=DEFAULT_QUERY_BUDGET,
        results_per_query=10,
    )

    assert len(provider.calls) == 8
    assert report["queries_attempted"] == 8
    assert report["queries_succeeded"] == 8
    assert report["accepted_signal_count"] >= 3
    assert report["canonical_market_coverage_unchanged"] == ["NO", "SE", "DE"]
    assert report["promotion_to_opportunity_allowed"] is False
    assert report["automatic_bid"] is False
    assert report["automatic_purchase"] is False


def test_missing_key_is_explicit_and_makes_no_request() -> None:
    def forbidden_factory(*args, **kwargs):
        raise AssertionError("provider must not initialize")

    report = collect_netherlands_market_signals(
        observed_at=NOW,
        environment={},
        provider_factory=forbidden_factory,
    )
    assert report["status"] == "BLOCKED_CONFIGURATION"
    assert report["block_reason"] == "BRAVE_SEARCH_API_KEY_MISSING"
    assert report["accepted_signal_count"] == 0
