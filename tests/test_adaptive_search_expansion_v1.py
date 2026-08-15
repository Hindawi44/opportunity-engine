from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.se_de_source_coverage_gap import (
    ADAPTIVE_SEARCH_EXPANSION_VERSION,
    SOURCE_QUERIES,
    _candidate_from_hit_with_reason,
    collect_manifest_se_de_source_coverage_gap,
)


def _manifest() -> dict:
    return {
        "sources": [
            {"market_code": "SE", "source_name": "Blinto", "artifact_dir": "inputs/se-blinto"},
            {"market_code": "DE", "source_name": "Riegermann", "artifact_dir": "inputs/de-riegermann"},
        ]
    }


def _prepare(tmp_path: Path) -> None:
    for relative in ("inputs/se-blinto", "inputs/de-riegermann"):
        (tmp_path / relative).mkdir(parents=True)


def test_adaptive_expansion_rescues_zero_primary_source(tmp_path: Path) -> None:
    _prepare(tmp_path)
    calls: list[str] = []
    rescued = SearchHit(
        title="Lagerauflösung Modehaus - Bekleidung und Schuhe",
        url="https://auktionen.restlos.com/auktionen/-/3000/lageraufloesung-modehaus/lose/1",
        description="Warenlager mit Bekleidung und Schuhen aus Geschäftsauflösung wird versteigert.",
        provider="Brave Search",
    )

    class FakeProvider:
        name = "Fake Brave"

        def search(self, query: str, *, count: int = 10):
            calls.append(query)
            if "site:restlos.com" in query and "Lagerauflösung" in query:
                return [rescued]
            return []

    report = collect_manifest_se_de_source_coverage_gap(
        _manifest(),
        root=tmp_path,
        observed_at=datetime(2026, 8, 15, 9, 15, tzinfo=timezone.utc),
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, api_key, freshness: FakeProvider(),
    )

    assert report["requests_made"] == 9
    assert report["adaptive_search_expansion_version"] == ADAPTIVE_SEARCH_EXPANSION_VERSION
    assert report["adaptive_query_budget_total"] == 12
    assert report["adaptive_requests_made"] == 12
    assert report["combined_requests_made"] == 21
    assert report["adaptive_signal_count"] == 1
    assert report["signal_count"] == 1
    assert report["adaptive_rescued_source_count"] >= 1

    signal = next(
        signal
        for source in report["sources"]
        for signal in source["signals"]
        if signal["source_country"] == "DE"
    )
    metadata = signal["metadata"]
    assert metadata["adaptive_search_expansion_version"] == ADAPTIVE_SEARCH_EXPANSION_VERSION
    assert metadata["adaptive_parent_query_id"] == "de-restlos-insolvency-clothing-stock"
    assert metadata["adaptive_expansion_tier"] == 1
    assert metadata["promotion_to_opportunity_allowed"] is False
    assert report["top5_eligible"] is False
    assert report["automatic_purchase"] is False


def test_adaptive_expansion_respects_smaller_budget(tmp_path: Path) -> None:
    _prepare(tmp_path)
    calls: list[str] = []

    class FakeProvider:
        name = "Fake Brave"

        def search(self, query: str, *, count: int = 10):
            calls.append(query)
            return []

    report = collect_manifest_se_de_source_coverage_gap(
        _manifest(),
        root=tmp_path,
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, api_key, freshness: FakeProvider(),
        adaptive_max_requests=4,
    )

    assert report["requests_made"] == 9
    assert report["adaptive_query_budget_total"] == 4
    assert report["adaptive_requests_made"] == 4
    assert report["combined_requests_made"] == 13
    assert len(calls) == 13
    # Germany wins ties in V1, so a four-request adaptive budget explores its
    # four zero-yield sources before Sweden.
    adaptive_calls = calls[9:]
    assert len(adaptive_calls) == 4
    assert all(
        any(domain in query for domain in (
            "online-versteigerungen.ht-kg.de",
            "sen-sen.de",
            "restlos.com",
            "versteigerungskalender.de",
        ))
        for query in adaptive_calls
    )


def test_run143_budi_category_snippet_is_rejected() -> None:
    hit = SearchHit(
        title="Konkursauktion på Restaurangutrustning & inredning - Budi Auktioner",
        url="https://www.budi.se/auktioner/8833/stockholm/restaurangutrustning-inredning",
        description=(
            "Kategorier Kläder & Skor Inredning & Möbler Elektronik & IT Diverse Musik "
            "Restaurang & Kök Verktyg Alla filter | Kassasystem, restaurangmöbler, "
            "kylar, belysning m.m."
        ),
        provider="Brave Search",
    )

    candidate, reason = _candidate_from_hit_with_reason(
        hit,
        market_code="SE",
        source_query=SOURCE_QUERIES["SE"][0],
        rank=1,
        observed_at=datetime(2026, 8, 15, 9, 15, tzinfo=timezone.utc),
    )

    assert candidate is None
    assert reason == "CLOTHING_RELEVANCE_MISSING"


def test_no_adaptive_requests_when_primary_sources_are_productive(tmp_path: Path) -> None:
    _prepare(tmp_path)

    class FakeProvider:
        name = "Fake Brave"

        def search(self, query: str, *, count: int = 10):
            if "site:budi.se" in query:
                return [SearchHit(title="Kläder från konkursauktion", url="https://www.budi.se/objekt/1/klader", description="Varulager med kläder från konkurs.", provider="Brave Search")]
            if "site:auktion.kronofogden.se" in query:
                return [SearchHit(title="Kläder och skor på auktion", url="https://auktion.kronofogden.se/auk/1", description="Varuparti med kläder och skor.", provider="Brave Search")]
            if "site:psauction.se" in query:
                return [SearchHit(title="Klädbutik i konkurs", url="https://psauction.se/item/view/1/klader", description="Varulager med kläder säljs på auktion.", provider="Brave Search")]
            if "site:klaravik.se" in query:
                return [SearchHit(title="Klädbutik - varulager", url="https://www.klaravik.se/auktion/produkt/1/", description="Konkursparti med kläder och skor.", provider="Brave Search")]
            if "site:allabolag.se" in query:
                return [SearchHit(title="Mode Kläder AB - Konkurs inledd", url="https://www.allabolag.se/foretag/mode-klader-ab/1", description="Detaljhandel med kläder och konfektion. Konkurs inledd.", provider="Brave Search")]
            if "site:online-versteigerungen.ht-kg.de" in query:
                return [SearchHit(title="Insolvenzversteigerung Mode GmbH", url="https://online-versteigerungen.ht-kg.de/de/Auktionen/Mode/1", description="Warenbestand mit Bekleidung und Textil.", provider="Brave Search")]
            if "site:sen-sen.de" in query:
                return [SearchHit(title="Textil Warenbestand Bekleidung", url="https://www.sen-sen.de/php/t1", description="Liquidation mit Bekleidung und Mode.", provider="Brave Search")]
            if "site:restlos.com" in query:
                return [SearchHit(title="Insolvenzauktion Bekleidung", url="https://auktionen.restlos.com/auktionen/-/1/lose/1", description="Warenbestand Bekleidung wird versteigert.", provider="Brave Search")]
            if "site:versteigerungskalender.de" in query:
                return [SearchHit(title="Clothing Mode GmbH Insolvenz", url="https://www.versteigerungskalender.de/insolvenzkalender/mode-gmbh", description="Insolvenz im Textilhandel und Bekleidung.", provider="Brave Search")]
            return []

    report = collect_manifest_se_de_source_coverage_gap(
        _manifest(),
        root=tmp_path,
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, api_key, freshness: FakeProvider(),
    )

    assert report["signal_count"] == 9
    assert report["requests_made"] == 9
    assert report["adaptive_requests_made"] == 0
    assert report["combined_requests_made"] == 9
