from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from opportunity_engine.discovery.france_market_discovery import (
    FRANCE_DISCOVERY_QUERIES,
    MATCHING_QUALITY_VERSION,
    collect_france_market_signals,
    france_signal_from_hit,
)
from opportunity_engine.discovery.search_provider import SearchHit


NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)


def _query(intent: str):
    return next(item for item in FRANCE_DISCOVERY_QUERIES if item.intent == intent)


class FakeProvider:
    def __init__(self, hits_by_query: dict[str, list[SearchHit]]) -> None:
        self.hits_by_query = hits_by_query
        self.calls: list[tuple[str, int]] = []

    @property
    def name(self) -> str:
        return "Fake Brave"

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        self.calls.append((query, count))
        return self.hits_by_query.get(query, [])[:count]


def test_bodacc_official_liquidation_is_signal_only_and_domain_bounded() -> None:
    query = _query("OFFICIAL_INSOLVENCY")
    hit = SearchHit(
        title="Liquidation judiciaire - PAPRIKA SAS",
        url="https://www.bodacc.fr/pages/annonces-commerciales-detail/?q.id=id:A202612345678",
        description=(
            "Dénomination : PAPRIKA SAS Forme juridique : Société par actions simplifiée "
            "Activité : vente de vêtements prêt-à-porter. Jugement prononçant la liquidation judiciaire."
        ),
        provider="Fake Brave",
    )
    signal = france_signal_from_hit(hit, query=query, rank=1, observed_at=NOW)
    assert signal is not None
    payload = signal.model_dump(mode="json")
    assert payload["source_country"] == "FR"
    assert payload["metadata"]["source_scope"] == "OFFICIAL_PUBLIC_SOURCE"
    assert payload["metadata"]["matching_quality_version"] == MATCHING_QUALITY_VERSION
    assert payload["metadata"]["promotion_to_opportunity_allowed"] is False
    assert payload["metadata"]["automatic_purchase"] is False

    wrong_domain = SearchHit(
        title=hit.title,
        url="https://example.fr/paprika-liquidation",
        description=hit.description,
        provider="Fake Brave",
    )
    assert france_signal_from_hit(wrong_domain, query=query, rank=1, observed_at=NOW) is None


def test_word_boundaries_prevent_substring_noise() -> None:
    query = _query("INSOLVENCY_LIQUIDATION")
    noise = SearchHit(
        title="Une solution moderne pour les entreprises",
        url="https://example.fr/moderne",
        description="Présentation d'une plateforme de liquidation de données pour sociétés commerciales.",
        provider="Fake Brave",
    )
    # 'mode' inside 'moderne' must never count as fashion evidence.
    assert france_signal_from_hit(noise, query=query, rank=1, observed_at=NOW) is None


def test_stocklot_requires_specific_buyer_facing_offer_not_editorial_article() -> None:
    query = _query("STOCKLOT_WHOLESALE")
    editorial = SearchHit(
        title="Le marché du stock de vêtements en France",
        url="https://news.example.fr/article-stock-vetements",
        description="Analyse du stock marchandises et du textile dans les magasins.",
        provider="Fake Brave",
    )
    assert france_signal_from_hit(editorial, query=query, rank=1, observed_at=NOW) is None

    live_false_positive = SearchHit(
        title="Le Rachat de Stock Vêtements : Levier de Croissance ou Aubaine pour les Commerçants ?",
        url="https://www.mydestockage.com/blog/boost/le-rachat-de-stock-vetements",
        description=(
            "On propose des lots de vêtements en gros. Un bon grossiste rachats de stocks "
            "vous accompagne. Déstockage, lots et prix sont expliqués dans ce guide."
        ),
        provider="Fake Brave",
    )
    assert france_signal_from_hit(live_false_positive, query=query, rank=1, observed_at=NOW) is None

    sourcing_guide = SearchHit(
        title="Déstockage et grossiste pas cher : où chercher sans se faire arnaquer",
        url="https://destockageenligne.fr/grossiste-sourcing",
        description="Guide des lots de vêtements et marchés de déstockage en ligne.",
        provider="Fake Brave",
    )
    assert france_signal_from_hit(sourcing_guide, query=query, rank=1, observed_at=NOW) is None

    offer = SearchHit(
        title="Lot de vêtements à vendre - déstockage professionnel",
        url="https://stock.example.fr/lot-vetements-500",
        description="500 pièces de prêt-à-porter en lot, prix disponible, stock à vendre.",
        provider="Fake Brave",
    )
    signal = france_signal_from_hit(offer, query=query, rank=1, observed_at=NOW)
    assert signal is not None
    payload = signal.model_dump(mode="json")
    assert payload["metadata"]["commercial_action_terms"]
    assert payload["metadata"]["inventory_offer_terms"]


def test_generic_auction_homepages_and_unrelated_stock_sale_are_rejected() -> None:
    query = _query("AUCTION_LOTS")
    for title, url, description in (
        (
            "Toutes les ventes aux enchères | Vavato",
            "https://www.vavato.com/fr/auctions",
            "Vêtements pour homme, chaussures, textile et beaucoup d'autres catégories. Enchères en cours.",
        ),
        (
            "Voir toutes nos enchères | Surplex",
            "https://www.surplex.com/fr/auctions",
            "Tous les lots industriels. Catégories textile, machines, chimie et équipements. Prix et enchères.",
        ),
        (
            "Voir toutes nos enchères | Troostwijk Auctions",
            "https://www.troostwijkauctions.com/fr/auctions",
            "Parcourez les lots. Catégories vêtements, chaussures et équipements. Enchères en ligne.",
        ),
        (
            "Après sa liquidation judiciaire, l’Intermarché a vendu aux enchères ses stocks et équipements",
            "https://www.vosgesmatin.fr/economie/intermarche-vente",
            "Réserve du magasin avec produits d'épicerie. Une rubrique textile est aussi citée sur le site.",
        ),
    ):
        hit = SearchHit(title=title, url=url, description=description, provider="Fake Brave")
        assert france_signal_from_hit(hit, query=query, rank=1, observed_at=NOW) is None

    specific = SearchHit(
        title="Vente aux enchères - stock de vêtements prêt-à-porter - lot 1048 pièces",
        url="https://auction.example.fr/stock-vetements-1048",
        description="Lot judiciaire de vêtements après liquidation judiciaire, vente aux enchères.",
        provider="Fake Brave",
    )
    assert france_signal_from_hit(specific, query=query, rank=1, observed_at=NOW) is not None


def test_bridal_query_rejects_generic_fashion_and_wedding_budget_editorial() -> None:
    query = _query("BRIDAL_LIQUIDATION")
    generic = SearchHit(
        title="Liquidation judiciaire d'une boutique de vêtements",
        url="https://example.fr/liquidation-mode",
        description="Stock de prêt-à-porter et chaussures en liquidation judiciaire.",
        provider="Fake Brave",
    )
    assert france_signal_from_hit(generic, query=query, rank=1, observed_at=NOW) is None

    live_budget_false_positive = SearchHit(
        title="Budget robe de mariée : faire la différence entre prix affiché et coût réel",
        url="https://www.la-mariee.fr/budget-robe-de-mariee",
        description="Les périodes de soldes ou de déstockage en boutique de mariage existent.",
        provider="Fake Brave",
    )
    assert france_signal_from_hit(live_budget_false_positive, query=query, rank=1, observed_at=NOW) is None

    bridal = SearchHit(
        title="Boutique de mariage en liquidation judiciaire - robes de mariée en stock",
        url="https://example.fr/robes-mariee-liquidation",
        description="Stock de robes de mariée et accessoires de mariage mis en vente.",
        provider="Fake Brave",
    )
    assert france_signal_from_hit(bridal, query=query, rank=1, observed_at=NOW) is not None


def test_real_legal_insolvency_signal_with_concrete_french_entity_survives_gate() -> None:
    query = _query("INSOLVENCY_LIQUIDATION")
    hit = SearchHit(
        title="Annonce légale #91502917",
        url="https://www.lagazettefrance.fr/annonce-legale/91502917",
        description=(
            "Redressement judiciaire. SAS KANA BEACH, RCS BREST 339 792 012. "
            "Achat et vente de tous vêtements de prêt-à-porter, chaussures et accessoires."
        ),
        provider="Fake Brave",
    )
    signal = france_signal_from_hit(hit, query=query, rank=1, observed_at=NOW)
    assert signal is not None
    assert signal.metadata["intent"] == "INSOLVENCY_LIQUIDATION"


def test_collection_valid_zero_is_acceptable() -> None:
    provider = FakeProvider({})
    report = collect_france_market_signals(
        observed_at=NOW,
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, key, freshness: provider,
    )
    assert report["status"] == "VALID_ZERO"
    assert report["matching_quality_version"] == MATCHING_QUALITY_VERSION
    assert report["queries_attempted"] == len(FRANCE_DISCOVERY_QUERIES)
    assert report["queries_succeeded"] == len(FRANCE_DISCOVERY_QUERIES)
    assert report["accepted_signal_count"] == 0
    assert report["errors"] == []


def test_collection_deduplicates_same_url_across_queries() -> None:
    hit = SearchHit(
        title="Vente aux enchères judiciaire - stock de vêtements",
        url="https://www.interencheres.com/biens-equipement/vente-stock/lot-123",
        description="Lot judiciaire de 1000 pièces de prêt-à-porter après liquidation judiciaire.",
        provider="Fake Brave",
    )
    auction = _query("JUDICIAL_AUCTION_STOCK")
    generic = _query("AUCTION_LOTS")
    provider = FakeProvider({auction.query: [hit], generic.query: [hit]})
    report = collect_france_market_signals(
        observed_at=NOW,
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, key, freshness: provider,
    )
    assert report["accepted_signal_count"] == 1
    assert report["duplicate_result_count"] >= 1
