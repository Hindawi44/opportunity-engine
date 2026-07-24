from __future__ import annotations

from opportunity_engine.discovery.classifier import classify_candidate
from opportunity_engine.discovery.live_search import run_live_discovery
from opportunity_engine.discovery.models import DiscoveryCandidate
from opportunity_engine.discovery.quality_engine import assess_quality
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider


class FakeProvider(SearchProvider):
    name = "fake"

    def search(self, query: str, *, count: int = 10):
        return [
            SearchHit(
                title="Komplett varelager fra klesbutikk selges",
                url="https://auksjon.no/lot/123",
                description="Hele lageret med klær og butikkinnredning selges etter avvikling.",
                provider=self.name,
            ),
        ]


def test_quality_engine_scores_confirmed_commercial_inventory():
    result = classify_candidate(
        DiscoveryCandidate(
            title="Komplett varelager fra klesbutikk selges",
            url="https://auksjon.no/lot/123",
            source="test",
            discovered_at="2026-07-24T00:00:00+00:00",
            text="Hele lageret med klær og butikkinnredning selges etter avvikling.",
            location="Oslo",
            price_nok=100000,
        )
    )
    quality = assess_quality(result)
    assert quality.score == 100
    assert quality.band == "HIGH"
    assert quality.reasons


def test_quality_engine_is_opt_in_and_preserves_legacy_contract():
    legacy = run_live_discovery(
        ["varelager klær Norge"],
        FakeProvider(),
        discovered_at="2026-07-24T00:00:00+00:00",
        apply_result_filter=True,
    )
    assert legacy["schema_version"] == "discovery-1.1"
    assert legacy["quality_engine_applied"] is False
    assert legacy["quality_version"] is None
    assert "quality" not in legacy["classified_results"][0]

    scored = run_live_discovery(
        ["varelager klær Norge"],
        FakeProvider(),
        discovered_at="2026-07-24T00:00:00+00:00",
        apply_result_filter=True,
        apply_quality_engine=True,
    )
    assert scored["schema_version"] == "discovery-1.1"
    assert scored["quality_engine_applied"] is True
    assert scored["quality_version"] == "discovery-1.6"
    assert scored["quality_counts"]["HIGH"] + scored["quality_counts"]["REVIEW"] + scored["quality_counts"]["LOW"] == 1
    assert scored["classified_results"][0]["quality"]["score"] > 0
