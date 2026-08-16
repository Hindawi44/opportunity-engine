from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from opportunity_engine.discovery.italy_market_discovery import (
    DEFAULT_QUERY_BUDGET,
    FEED_FAMILY,
    ITALY_DISCOVERY_QUERIES,
    ItalyDiscoveryQuery,
    collect_italy_market_signals,
    italy_signal_from_hit,
)
from opportunity_engine.discovery.search_provider import SearchHit


NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)


def test_query_pack_covers_core_italy_intents() -> None:
    intents = {query.intent for query in ITALY_DISCOVERY_QUERIES}
    assert DEFAULT_QUERY_BUDGET == 7
    assert intents == {
        "OFFICIAL_JUDICIAL_SALES",
        "INSOLVENCY_LIQUIDATION",
        "BUSINESS_CLOSURE",
        "STOCKLOT_WHOLESALE",
        "AUCTION_LOTS",
        "BRIDAL_LIQUIDATION",
        "WAREHOUSE_CLEARANCE",
    }
    official = ITALY_DISCOVERY_QUERIES[0]
    assert official.official_only is True
    assert "pvp.giustizia.it" in official.query
    assert any("abiti da sposa" in query.query for query in ITALY_DISCOVERY_QUERIES)
    assert any("rimanenze di magazzino" in query.query for query in ITALY_DISCOVERY_QUERIES)


def test_accepts_public_fashion_liquidation_as_signal_only() -> None:
    query = ITALY_DISCOVERY_QUERIES[1]
    signal = italy_signal_from_hit(
        SearchHit(
            title="Liquidazione giudiziale di negozio di abbigliamento",
            url="https://example.it/liquidazione-moda?utm_source=test",
            description="Vendita del magazzino moda e dei capi rimasti.",
            provider="Fake Brave",
        ),
        query=query,
        rank=1,
        observed_at=NOW,
    )
    assert signal is not None
    assert signal.source_country == "IT"
    assert signal.signal_type.value == "INSOLVENCY_OR_LIQUIDATION"
    assert signal.metadata["feed_family"] == FEED_FAMILY
    assert signal.metadata["inventory_domain"] == "CLOTHING_FASHION"
    assert signal.metadata["source_page_verification_required"] is True
    assert signal.metadata["promotion_to_opportunity_allowed"] is False
    assert signal.metadata["automatic_purchase"] is False
    assert str(signal.source_url) == "https://example.it/liquidazione-moda"


def test_accepts_bridal_stock_and_keeps_bridal_domain() -> None:
    query = next(q for q in ITALY_DISCOVERY_QUERIES if q.intent == "BRIDAL_LIQUIDATION")
    signal = italy_signal_from_hit(
        SearchHit(
            title="Atelier sposa in liquidazione - campionario abiti da sposa",
            url="https://atelier.example.it/stock-spose",
            description="Stock e campionario disponibili dopo cessazione attività.",
            provider="Fake Brave",
        ),
        query=query,
        rank=2,
        observed_at=NOW,
    )
    assert signal is not None
    assert signal.metadata["inventory_domain"] == "BRIDAL"
    assert signal.metadata["intent"] == "BRIDAL_LIQUIDATION"
    assert signal.metadata["top5_eligible"] is False


def test_rejects_ordinary_retail_page_without_liquidation_or_stock_event() -> None:
    query = ITALY_DISCOVERY_QUERIES[2]
    signal = italy_signal_from_hit(
        SearchHit(
            title="Nuova collezione moda donna",
            url="https://shop.example.it/nuova-collezione",
            description="Abbigliamento e vestiti della nuova stagione.",
            provider="Fake Brave",
        ),
        query=query,
        rank=1,
        observed_at=NOW,
    )
    assert signal is None


def test_official_query_accepts_only_exact_pvp_domain() -> None:
    query = ITALY_DISCOVERY_QUERIES[0]
    accepted = italy_signal_from_hit(
        SearchHit(
            title="Lotto abbigliamento e calzature - asta giudiziaria",
            url="https://pvp.giustizia.it/pvp/it/dettaglio_annuncio.page?id=123",
            description="Vendita giudiziaria di lotto abbigliamento.",
            provider="Fake Brave",
        ),
        query=query,
        rank=1,
        observed_at=NOW,
    )
    rejected = italy_signal_from_hit(
        SearchHit(
            title="Lotto abbigliamento e calzature - asta giudiziaria",
            url="https://not-pvp.example.it/lotto-123",
            description="Vendita giudiziaria di lotto abbigliamento.",
            provider="Fake Brave",
        ),
        query=query,
        rank=2,
        observed_at=NOW,
    )
    assert accepted is not None
    assert accepted.metadata["source_scope"] == "OFFICIAL_JUDICIAL_SALES"
    assert rejected is None


def test_matching_uses_term_boundaries_for_moda_and_asta() -> None:
    pvp_query = ITALY_DISCOVERY_QUERIES[0]
    false_moda = italy_signal_from_hit(
        SearchHit(
            title="Dettaglio Annuncio - PVP Giustizia",
            url="https://pvp.giustizia.it/pvp/it/detail_annuncio.page?idAnnuncio=4612723",
            description=(
                "Modalità di vendita. Prezzo base d'asta 309.726 euro. "
                "Beni inclusi nel lotto."
            ),
            provider="Fake Brave",
        ),
        query=pvp_query,
        rank=1,
        observed_at=NOW,
    )
    assert false_moda is None

    bridal_query = next(q for q in ITALY_DISCOVERY_QUERIES if q.intent == "BRIDAL_LIQUIDATION")
    false_asta = italy_signal_from_hit(
        SearchHit(
            title="Outlet abbigliamento e scarpe",
            url="https://www.secondastrada.example/it",
            description="Vasto assortimento di abbigliamento e scarpe tutto l'anno.",
            provider="Fake Brave",
        ),
        query=bridal_query,
        rank=1,
        observed_at=NOW,
    )
    assert false_asta is None


def test_bridal_query_requires_explicit_bridal_evidence_in_hit() -> None:
    query = next(q for q in ITALY_DISCOVERY_QUERIES if q.intent == "BRIDAL_LIQUIDATION")
    signal = italy_signal_from_hit(
        SearchHit(
            title="Bancarotta di impresa del settore abbigliamento",
            url="https://news.example.it/fallimento-moda",
            description="Fallimento di una ditta di abbigliamento all'ingrosso.",
            provider="Fake Brave",
        ),
        query=query,
        rank=1,
        observed_at=NOW,
    )
    assert signal is None


def test_stocklot_query_rejects_editorial_inventory_article_without_commercial_action() -> None:
    query = next(q for q in ITALY_DISCOVERY_QUERIES if q.intent == "STOCKLOT_WHOLESALE")
    signal = italy_signal_from_hit(
        SearchHit(
            title="Invenduti moda, nuove regole UE per il tessile",
            url="https://news.example.it/invenduti-moda",
            description=(
                "Le imprese devono gestire lo stock accumulato a magazzino e le "
                "rimanenze di magazzino di abbigliamento e calzature."
            ),
            provider="Fake Brave",
        ),
        query=query,
        rank=1,
        observed_at=NOW,
    )
    assert signal is None


def test_stocklot_query_keeps_commercial_stock_source() -> None:
    query = next(q for q in ITALY_DISCOVERY_QUERIES if q.intent == "STOCKLOT_WHOLESALE")
    signal = italy_signal_from_hit(
        SearchHit(
            title="Rimanenze moda: stock abbigliamento all'ingrosso",
            url="https://stock.example.it/rimanenze-moda",
            description="Vendere e acquistare lotti di rimanenze di magazzino.",
            provider="Fake Brave",
        ),
        query=query,
        rank=1,
        observed_at=NOW,
    )
    assert signal is not None
    assert "vendere" in signal.metadata["commercial_action_terms"]


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    @property
    def name(self) -> str:
        return "Fake Brave"

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        self.calls.append((query, count))
        if "site:pvp.giustizia.it" in query:
            return [
                SearchHit(
                    title="Lotto abbigliamento - asta giudiziaria",
                    url="https://pvp.giustizia.it/pvp/it/dettaglio_annuncio.page?id=7",
                    description="Vendita giudiziaria di abbigliamento e calzature.",
                    provider="Fake Brave",
                )
            ]
        if "abiti da sposa" in query:
            return [
                SearchHit(
                    title="Atelier sposa cessazione attività",
                    url="https://bridal.example.it/chiusura",
                    description="Campionario abiti da sposa e stock in liquidazione.",
                    provider="Fake Brave",
                )
            ]
        return [
            SearchHit(
                title="Stock abbigliamento in liquidazione",
                url="https://stock.example.it/lotto",
                description="Rimanenze di magazzino moda in vendita.",
                provider="Fake Brave",
            )
        ]


def test_collection_is_bounded_deduplicated_and_reports_domains() -> None:
    provider = FakeProvider()

    report = collect_italy_market_signals(
        observed_at=NOW,
        environment={"BRAVE_SEARCH_API_KEY": "secret"},
        provider_factory=lambda market, key, freshness: provider,
        query_budget=DEFAULT_QUERY_BUDGET,
        results_per_query=10,
    )

    assert len(provider.calls) == 7
    assert report["queries_attempted"] == 7
    assert report["queries_succeeded"] == 7
    assert report["accepted_signal_count"] == 3
    assert report["duplicate_result_count"] == 4
    assert report["independent_domain_count"] == 3
    assert report["official_pvp_enabled"] is True
    assert report["promotion_to_opportunity_allowed"] is False
    assert report["automatic_bid"] is False
    assert report["automatic_purchase"] is False
    assert {signal["metadata"]["inventory_domain"] for signal in report["signals"]} == {
        "CLOTHING_FASHION",
        "BRIDAL",
    }


def test_missing_key_is_explicit_and_makes_no_request() -> None:
    def forbidden_factory(*args, **kwargs):
        raise AssertionError("provider must not initialize")

    report = collect_italy_market_signals(
        observed_at=NOW,
        environment={},
        provider_factory=forbidden_factory,
    )
    assert report["status"] == "BLOCKED_CONFIGURATION"
    assert report["block_reason"] == "BRAVE_SEARCH_API_KEY_MISSING"
    assert report["accepted_signal_count"] == 0


def test_invalid_budget_is_rejected() -> None:
    try:
        collect_italy_market_signals(environment={}, query_budget=99)
    except ValueError as exc:
        assert "query_budget" in str(exc)
    else:
        raise AssertionError("expected ValueError")
