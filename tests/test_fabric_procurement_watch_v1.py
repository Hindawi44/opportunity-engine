from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from opportunity_engine.discovery.fabric_procurement_watch import (
    FEED_FAMILY,
    SOURCES,
    collect_fabric_procurement_watch,
    procurement_candidate_from_hit,
)
from opportunity_engine.discovery.search_provider import SearchHit


NOW = datetime(2026, 8, 5, 21, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts/build_domain_market_intelligence_feed.py"
CORE_SCRIPT = ROOT / "scripts/build_domain_market_intelligence_feed_core.py"


def test_watch_uses_verified_official_domains_with_prato_expansion() -> None:
    assert [source.domain for source in SOURCES] == [
        "evaresource.com",
        "fabrichouse.com",
        "tessutistockprato.it",
        "tessutiastock.com",
        "bridalfabrics.com",
    ]
    assert [source.country for source in SOURCES] == ["IT", "IT", "IT", "IT", "GB"]
    assert [source.location for source in SOURCES[2:4]] == ["Prato, IT", "Prato, IT"]
    assert all(f"site:{source.domain}" in source.query for source in SOURCES)


def test_accepts_high_value_eva_deadstock_fabric_result() -> None:
    source = SOURCES[0]
    candidate = procurement_candidate_from_hit(
        SearchHit(
            title="Ivory pure silk organza deadstock deal €24.50/m",
            url="https://www.evaresource.com/products/ivory-silk-organza?utm_source=test",
            description="Final quantity in stock for bridal and wedding dresses.",
            provider="Brave Search",
        ),
        source=source,
        observed_at=NOW,
    )

    assert candidate is not None
    assert candidate["source_name"] == "EVA re-source"
    assert candidate["currency"] == "EUR"
    assert candidate["price"] == 24.5
    assert candidate["procurement_relevance_score"] == 100
    assert candidate["source_url"] == (
        "https://www.evaresource.com/products/ivory-silk-organza"
    )
    assert candidate["promotion_to_opportunity_allowed"] is False
    assert candidate["automatic_purchase"] is False


def test_accepts_prato_stock_result_in_italian() -> None:
    candidate = procurement_candidate_from_hit(
        SearchHit(
            title="Tessuti a stock in lana e mohair pronti in magazzino €18.50",
            url="https://www.tessutistockprato.it/en-gb/il-magazzino",
            description="Tessuti italiani a stock e pronta consegna dal magazzino di Prato.",
            provider="Brave Search",
        ),
        source=SOURCES[2],
        observed_at=NOW,
    )

    assert candidate is not None
    assert candidate["source_name"] == "Verian Tessuti a Stock"
    assert candidate["source_kind"] == "PRATO_DEADSTOCK"
    assert candidate["source_country"] == "IT"
    assert candidate["location"] == "Prato, IT"
    assert candidate["currency"] == "EUR"
    assert candidate["price"] == 18.5
    assert "tessuti" in candidate["fabric_terms"]
    assert "magazzino" in candidate["value_terms"]
    assert candidate["not_a_liquidation_opportunity"] is True


def test_rejects_result_from_unapproved_domain() -> None:
    candidate = procurement_candidate_from_hit(
        SearchHit(
            title="Ivory silk deadstock sale €10",
            url="https://fake-eva.example/products/silk",
            description="Bridal organza in stock.",
            provider="Brave Search",
        ),
        source=SOURCES[0],
        observed_at=NOW,
    )
    assert candidate is None


def test_accepts_specialist_bridal_fabric_without_deadstock_claim() -> None:
    candidate = procurement_candidate_from_hit(
        SearchHit(
            title="Ivory bridal lace for wedding dresses £42.00",
            url="https://www.bridalfabrics.com/products/ivory-lace",
            description="Sample available from a specialist bridal fabric supplier.",
            provider="Brave Search",
        ),
        source=SOURCES[4],
        observed_at=NOW,
    )

    assert candidate is not None
    assert candidate["source_kind"] == "SPECIALIST_BRIDAL_SUPPLIER"
    assert candidate["currency"] == "GBP"
    assert candidate["price"] == 42.0
    assert candidate["not_a_liquidation_opportunity"] is True


def test_rejects_generic_non_fabric_page() -> None:
    candidate = procurement_candidate_from_hit(
        SearchHit(
            title="About our company",
            url="https://www.fabrichouse.com/int/about-us",
            description="Learn about our history and team.",
            provider="Brave Search",
        ),
        source=SOURCES[1],
        observed_at=NOW,
    )
    assert candidate is None


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    @property
    def name(self) -> str:
        return "Fake Brave"

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        self.calls.append((query, count))
        if "evaresource.com" in query:
            return [
                SearchHit(
                    title="Ivory silk satin deadstock deal €19.90/m",
                    url="https://evaresource.com/products/ivory-silk-satin",
                    description="Final quantity in stock for bridal use.",
                    provider=self.name,
                )
            ]
        if "fabrichouse.com" in query:
            return [
                SearchHit(
                    title="White duchesse satin deadstock sale €31.00/m",
                    url="https://www.fabrichouse.com/int/product/white-duchesse",
                    description="Premium fabric stock and sample service.",
                    provider=self.name,
                )
            ]
        if "tessutistockprato.it" in query:
            return [
                SearchHit(
                    title="Tessuti a stock lana e seta €18.50",
                    url="https://www.tessutistockprato.it/en-gb/il-magazzino",
                    description="Magazzino a Prato con tessuti in pronta consegna.",
                    provider=self.name,
                )
            ]
        if "tessutiastock.com" in query:
            return [
                SearchHit(
                    title="Stock tessuti in rotoli: lino, pizzo e velluto €12.00",
                    url="https://www.tessutiastock.com/contatti",
                    description="Tessuti italiani a stock venduti in rotoli e al metro.",
                    provider=self.name,
                )
            ]
        return [
            SearchHit(
                title="Ivory wedding tulle and bridal lace £28.00",
                url="https://www.bridalfabrics.com/products/ivory-tulle",
                description="Fabric sample available for bridal designers.",
                provider=self.name,
            )
        ]


def test_collection_is_bounded_to_five_official_source_requests() -> None:
    providers: list[FakeProvider] = []

    def factory(country: str, api_key: str, freshness: str | None) -> FakeProvider:
        assert country in {"IT", "GB"}
        assert api_key == "secret"
        assert freshness == "pm"
        provider = FakeProvider()
        providers.append(provider)
        return provider

    report = collect_fabric_procurement_watch(
        observed_at=NOW,
        environment={"BRAVE_SEARCH_API_KEY": "secret"},
        provider_factory=factory,
        results_per_source=8,
    )

    assert report["feed_family"] == FEED_FAMILY
    assert report["search_language"] == "en+it"
    assert report["query_budget_total"] == 5
    assert report["requests_made"] == 5
    assert report["candidate_count"] == 5
    assert report["status_counts"] == {"SUCCESS": 5}
    assert report["not_part_of_opportunity_top5"] is True
    assert report["automatic_purchase"] is False
    assert len(providers) == 5
    assert all(len(provider.calls) == 1 for provider in providers)


def test_missing_brave_key_is_explicit_and_makes_no_request() -> None:
    def forbidden_factory(*args, **kwargs):
        raise AssertionError("provider must not be initialized")

    report = collect_fabric_procurement_watch(
        observed_at=NOW,
        environment={},
        provider_factory=forbidden_factory,
    )

    assert report["requests_made"] == 0
    assert report["candidate_count"] == 0
    assert report["status_counts"] == {"BLOCKED_CONFIGURATION": 5}
    assert all(
        source["block_reason"] == "BRAVE_SEARCH_API_KEY_MISSING"
        for source in report["sources"]
    )


def test_results_limit_is_bounded() -> None:
    try:
        collect_fabric_procurement_watch(
            observed_at=NOW,
            environment={},
            results_per_source=11,
        )
    except ValueError as exc:
        assert "results_per_source" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_daily_builder_wraps_existing_core_and_attaches_procurement_artifact() -> None:
    text = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert CORE_SCRIPT.exists()
    assert "collect_fabric_procurement_watch" in text
    assert 'fabric-procurement-watch.json' in text
    assert 'brief["fabric_procurement_watch"]' in text
    assert '"top_procurement_candidates"' in text
    assert '"automatic_purchase": False' in text
