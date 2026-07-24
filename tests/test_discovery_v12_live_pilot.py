from __future__ import annotations

from scripts.run_discovery_v12_live_pilot import build_mobile_report
from opportunity_engine.discovery.live_search import run_live_discovery
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider


class FakeProvider(SearchProvider):
    name = "fake-live"

    def search(self, query: str, *, count: int = 10):
        return [
            SearchHit(
                title="Komplett varelager klær til salgs",
                url="https://example.no/confirmed",
                description="Hele lageret selges. Pris på forespørsel.",
                provider=self.name,
            ),
            SearchHit(
                title="Klesbutikk konkurs",
                url="https://example.no/lead",
                description="Konkursbo med mulig varelager.",
                provider=self.name,
            ),
            SearchHit(
                title="Brukt jakke",
                url="https://example.no/rejected",
                description="Én jakke selges privat.",
                provider=self.name,
            ),
            SearchHit(
                title="Duplicate sale",
                url="https://example.no/confirmed",
                description="same URL",
                provider=self.name,
            ),
        ]


def _report():
    report = run_live_discovery(
        ["varelager klær Norge"],
        FakeProvider(),
        discovered_at="2026-07-24T16:00:00+00:00",
        results_per_query=10,
    )
    report["pilot_topic"] = "CLOTHING_INVENTORY"
    return report


def test_v12_live_pilot_contract():
    report = _report()
    assert report["schema_version"] == "discovery-1.1"
    assert report["queries_submitted"] == 1
    assert report["candidates_received"] == 3
    assert report["duplicates_removed"] == 1
    assert report["confirmed_sales"] == 1
    assert report["follow_up_leads"] == 1
    assert report["rejected_results"] == 1
    assert len(report["canonical_opportunities"]) == 1
    assert report["automatic_purchase_decision"] is False
    assert report["status"] == "PASS"


def test_v13_mobile_report_is_compact_and_contains_links():
    output = build_mobile_report(_report(), limit=3)
    assert "DISCOVERY REPORT — MOBILE VIEW" in output
    assert "Confirmed sales: 1" in output
    assert "Needs contact: 1" in output
    assert "Rejected: 1" in output
    assert "https://example.no/confirmed" in output
    assert "https://example.no/lead" in output
    assert "Automatic purchase decision: NO" in output
    assert output.index("[SALE_CONFIRMED]") < output.index("[CONTACT_REQUIRED]")
