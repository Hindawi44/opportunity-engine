from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import opportunity_engine.discovery.fabric_procurement_watch as fabric_watch
from opportunity_engine.discovery.fabric_procurement_watch_cli_hook import (
    write_daily_fabric_procurement_watch,
)
from opportunity_engine.discovery.italy_textile_district_sources import (
    ITALY_TEXTILE_DISTRICT_SOURCES,
    collect_italy_district_expanded_fabric_watch,
)
from opportunity_engine.discovery.search_provider import SearchHit


NOW = datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc)


def test_como_and_biella_sources_are_bounded_official_domains() -> None:
    assert [source.domain for source in ITALY_TEXTILE_DISTRICT_SOURCES] == [
        "silklabitaly.com",
        "texitbiella.com",
    ]
    assert [source.location for source in ITALY_TEXTILE_DISTRICT_SOURCES] == [
        "Como, IT",
        "Biella, IT",
    ]
    assert [source.source_kind for source in ITALY_TEXTILE_DISTRICT_SOURCES] == [
        "COMO_SILK_STOCK",
        "BIELLA_WOOL_STOCK",
    ]
    assert all(source.country == "IT" for source in ITALY_TEXTILE_DISTRICT_SOURCES)
    assert all(f"site:{source.domain}" in source.query for source in ITALY_TEXTILE_DISTRICT_SOURCES)


class DistrictProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    @property
    def name(self) -> str:
        return "Fake Brave"

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        self.calls.append((query, count))
        if "silklabitaly.com" in query:
            return [
                SearchHit(
                    title="Stock service seta e satin disponibili al metro",
                    url="https://www.silklabitaly.com/",
                    description=(
                        "Tessuti in seta, raso, georgette e crepe de chine in stock service. "
                        "Vendita al metro dal distretto di Como."
                    ),
                    provider=self.name,
                )
            ]
        if "texitbiella.com" in query:
            return [
                SearchHit(
                    title="Vendita tessuti a stock lana e cashmere a Biella",
                    url="https://www.texitbiella.com/cosa-facciamo",
                    description=(
                        "Stock di tessuti selezionati in magazzino per grossisti, sarti e designer."
                    ),
                    provider=self.name,
                )
            ]
        return []


def test_daily_expansion_adds_two_queries_and_restores_base_collector_sources() -> None:
    providers: list[DistrictProvider] = []
    original_sources = fabric_watch.SOURCES

    def factory(country: str, api_key: str, freshness: str | None) -> DistrictProvider:
        assert country in {"IT", "GB"}
        assert api_key == "secret"
        assert freshness is None
        provider = DistrictProvider()
        providers.append(provider)
        return provider

    report = collect_italy_district_expanded_fabric_watch(
        observed_at=NOW,
        environment={"BRAVE_SEARCH_API_KEY": "secret"},
        provider_factory=factory,
        results_per_source=8,
        freshness=None,
    )

    assert report["feed_family"] == "FABRIC_DEADSTOCK_PROCUREMENT_FEED_V1"
    assert report["query_budget_total"] == 7
    assert report["requests_made"] == 7
    assert report["candidate_count"] == 2
    assert report["status_counts"] == {"VALID_ZERO": 5, "SUCCESS": 2}
    assert report["italy_textile_district_scope"] == ["Prato", "Como", "Biella"]
    assert report["district_candidate_counts"] == {"Prato": 0, "Como": 1, "Biella": 1}
    assert fabric_watch.SOURCES == original_sources
    assert len(providers) == 7
    assert all(len(provider.calls) == 1 for provider in providers)

    by_kind = {item["source_kind"]: item for item in report["candidates"]}
    assert by_kind["COMO_SILK_STOCK"]["location"] == "Como, IT"
    assert by_kind["COMO_SILK_STOCK"]["source_country"] == "IT"
    assert by_kind["BIELLA_WOOL_STOCK"]["location"] == "Biella, IT"
    assert by_kind["BIELLA_WOOL_STOCK"]["source_country"] == "IT"
    assert all(item["automatic_purchase"] is False for item in report["candidates"])


def test_daily_brief_surfaces_all_three_italian_textile_districts(tmp_path: Path) -> None:
    report = {
        "schema_version": "fabric-procurement-watch-1.0",
        "feed_family": "FABRIC_DEADSTOCK_PROCUREMENT_FEED_V1",
        "purpose": "TAILORING_SHOP_FABRIC_PROCUREMENT_INTELLIGENCE",
        "search_language": "en+it",
        "freshness": None,
        "approved_official_domains": [
            "tessutistockprato.it",
            "silklabitaly.com",
            "texitbiella.com",
        ],
        "query_budget_total": 7,
        "requests_made": 7,
        "status_counts": {"SUCCESS": 3},
        "candidate_count": 3,
        "italy_textile_district_scope": ["Prato", "Como", "Biella"],
        "district_candidate_counts": {"Prato": 1, "Como": 1, "Biella": 1},
        "candidates": [
            {
                "candidate_id": "fabric-watch:verian-prato:test",
                "source_name": "Verian Tessuti a Stock",
                "source_country": "IT",
                "source_kind": "PRATO_DEADSTOCK",
                "location": "Prato, IT",
                "title": "Tessuti a stock Prato",
                "source_url": "https://www.tessutistockprato.it/il-magazzino",
                "fabric_terms": ["tessuti"],
                "bridal_terms": [],
                "price": None,
                "currency": None,
                "quantity": None,
                "quantity_unit": None,
                "procurement_relevance_score": 75,
                "recommended_operator_action": "REVIEW_SAMPLE_PRICE_AND_SHIPPING",
            },
            {
                "candidate_id": "fabric-watch:silk-lab-como:test",
                "source_name": "Silk Lab Italy",
                "source_country": "IT",
                "source_kind": "COMO_SILK_STOCK",
                "location": "Como, IT",
                "title": "Stock service seta Como",
                "source_url": "https://www.silklabitaly.com/",
                "fabric_terms": ["seta"],
                "bridal_terms": [],
                "price": None,
                "currency": None,
                "quantity": None,
                "quantity_unit": None,
                "procurement_relevance_score": 75,
                "recommended_operator_action": "REVIEW_SAMPLE_PRICE_AND_SHIPPING",
            },
            {
                "candidate_id": "fabric-watch:texit-biella:test",
                "source_name": "Texit Italian Quality Textiles",
                "source_country": "IT",
                "source_kind": "BIELLA_WOOL_STOCK",
                "location": "Biella, IT",
                "title": "Tessuti a stock lana Biella",
                "source_url": "https://www.texitbiella.com/cosa-facciamo",
                "fabric_terms": ["lana", "tessuti"],
                "bridal_terms": [],
                "price": None,
                "currency": None,
                "quantity": None,
                "quantity_unit": None,
                "procurement_relevance_score": 75,
                "recommended_operator_action": "REVIEW_SAMPLE_PRICE_AND_SHIPPING",
            },
        ],
        "promotion_to_opportunity_allowed": False,
        "analysis_eligible": False,
        "top5_eligible": False,
        "automatic_contact": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }

    def fake_collector(**kwargs):
        assert kwargs["freshness"] is None
        return report

    brief_json = tmp_path / "domain-market-intelligence-brief.json"
    brief_json.write_text(json.dumps({"market_coverage": ["NO", "SE", "DE"]}), encoding="utf-8")
    brief_text = tmp_path / "domain-market-intelligence-brief.txt"
    brief_text.write_text("BASE BULLETIN\n", encoding="utf-8")

    write_daily_fabric_procurement_watch(
        tmp_path,
        environment={"BRAVE_SEARCH_API_KEY": "secret"},
        collector=fake_collector,
    )

    brief = json.loads(brief_json.read_text(encoding="utf-8"))
    section = brief["fabric_procurement_watch"]
    assert section["prato_candidate_count"] == 1
    assert section["como_candidate_count"] == 1
    assert section["biella_candidate_count"] == 1
    assert section["district_candidate_counts"] == {"Prato": 1, "Como": 1, "Biella": 1}
    assert section["top_como_candidates"][0]["location"] == "Como, IT"
    assert section["top_biella_candidates"][0]["location"] == "Biella, IT"
    assert section["automatic_purchase"] is False

    rendered = brief_text.read_text(encoding="utf-8")
    assert "[IT/Prato] Verian Tessuti a Stock" in rendered
    assert "[IT/Como] Silk Lab Italy" in rendered
    assert "[IT/Biella] Texit Italian Quality Textiles" in rendered
