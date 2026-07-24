from __future__ import annotations

from opportunity_engine.discovery.live_search import run_live_discovery
from opportunity_engine.discovery.models import DiscoveryCandidate
from opportunity_engine.discovery.result_filter import evaluate_candidate
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider


class FakeProvider(SearchProvider):
    name = "fake"

    def search(self, query: str, *, count: int = 10):
        return [
            SearchHit(
                title="Opphørssalg - hva er det?",
                url="https://ordliste.no/opphorssalg",
                description="Definisjon og synonym",
                provider=self.name,
            ),
            SearchHit(
                title="Komplett varelager fra klesbutikk selges",
                url="https://auksjon.no/lot/123",
                description="Hele lageret til salgs etter avvikling",
                provider=self.name,
            ),
            SearchHit(
                title="Sommerjakke til salgs",
                url="https://example.no/jakke",
                description="En jakke selges privat",
                provider=self.name,
            ),
        ]


def test_filter_rejects_dictionary_page():
    decision = evaluate_candidate(
        DiscoveryCandidate(
            title="Opphørssalg - hva er det?",
            url="https://ordliste.no/opphorssalg",
            source="test",
            discovered_at="2026-07-24T00:00:00+00:00",
            text="Definisjon og synonym",
        )
    )
    assert decision.keep is False
    assert decision.reason == "informational or dictionary page"


def test_filter_keeps_commercial_inventory_sale():
    decision = evaluate_candidate(
        DiscoveryCandidate(
            title="Komplett varelager fra klesbutikk selges",
            url="https://auksjon.no/lot/123",
            source="test",
            discovered_at="2026-07-24T00:00:00+00:00",
            text="Hele lageret til salgs etter avvikling",
        )
    )
    assert decision.keep is True
    assert decision.score > 0


def test_live_discovery_filters_before_classification_when_enabled():
    report = run_live_discovery(
        ["varelager klær Norge"],
        FakeProvider(),
        discovered_at="2026-07-24T00:00:00+00:00",
        apply_result_filter=True,
    )

    assert report["schema_version"] == "discovery-1.1"
    assert report["filter_version"] == "discovery-1.5"
    assert report["result_filter_applied"] is True
    assert report["hits_received"] == 3
    assert report["filtered_out_count"] == 2
    assert report["candidates_received"] == 1
    assert report["confirmed_sales"] == 1
    assert report["canonical_opportunities"]


def test_live_discovery_preserves_legacy_behavior_by_default():
    report = run_live_discovery(
        ["varelager klær Norge"],
        FakeProvider(),
        discovered_at="2026-07-24T00:00:00+00:00",
    )

    assert report["schema_version"] == "discovery-1.1"
    assert report["filter_version"] is None
    assert report["result_filter_applied"] is False
    assert report["filtered_out_count"] == 0
    assert report["candidates_received"] == 3
