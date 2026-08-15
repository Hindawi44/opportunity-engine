from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.se_de_source_coverage_gap import (
    SOURCE_QUERIES,
    _candidate_from_hit_with_reason,
    collect_manifest_se_de_source_coverage_gap,
)


def _manifest() -> dict:
    return {
        "sources": [
            {
                "market_code": "SE",
                "source_name": "Blinto",
                "artifact_dir": "inputs/se-blinto",
            },
            {
                "market_code": "DE",
                "source_name": "Riegermann",
                "artifact_dir": "inputs/de-riegermann",
            },
        ]
    }


def test_restaurant_equipment_false_positive_is_rejected() -> None:
    hit = SearchHit(
        title="Konkursauktion på Restaurangutrustning & inredning",
        url="https://www.budi.se/auktioner/8833/stockholm/restaurangutrustning-inredning",
        description="Restaurangutrustning och inredning från konkurs säljs på auktion.",
        provider="Brave Search",
    )

    candidate, reason = _candidate_from_hit_with_reason(
        hit,
        market_code="SE",
        source_query=SOURCE_QUERIES["SE"][0],
        rank=1,
        observed_at=datetime(2026, 8, 15, 8, 40, tzinfo=timezone.utc),
    )

    assert candidate is None
    assert reason == "CLOTHING_RELEVANCE_MISSING"


def test_source_yield_diagnostics_identify_productive_and_dead_queries(
    tmp_path: Path,
) -> None:
    for relative in ("inputs/se-blinto", "inputs/de-riegermann"):
        (tmp_path / relative).mkdir(parents=True)

    restaurant = SearchHit(
        title="Konkursauktion på Restaurangutrustning & inredning",
        url="https://www.budi.se/auktioner/8833/stockholm/restaurangutrustning-inredning",
        description="Restaurangutrustning och inredning från konkurs säljs på auktion.",
        provider="Brave Search",
    )
    clothing = SearchHit(
        title="Klädbutik i konkurs - varulager med kläder",
        url="https://psauction.se/item/view/200001/kladbutik-i-konkurs",
        description="Varulager med kläder, skor och accessoarer säljs på konkursauktion.",
        provider="Brave Search",
    )

    class FakeProvider:
        name = "Fake Brave"

        def search(self, query: str, *, count: int = 10):
            if "site:budi.se" in query:
                return [restaurant]
            if "site:psauction.se" in query:
                return [clothing]
            return []

    report = collect_manifest_se_de_source_coverage_gap(
        _manifest(),
        root=tmp_path,
        observed_at=datetime(2026, 8, 15, 8, 40, tzinfo=timezone.utc),
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, api_key, freshness: FakeProvider(),
    )

    assert report["source_yield_diagnostics_version"] == "SE_DE_SOURCE_YIELD_DIAGNOSTICS_V1"
    assert report["signal_count"] == 1

    by_market = {item["source_country"]: item for item in report["sources"]}
    se = by_market["SE"]
    de = by_market["DE"]

    by_source = {item["source_name"]: item for item in se["query_diagnostics"]}
    assert by_source["Budi Auktioner"]["result_count"] == 1
    assert by_source["Budi Auktioner"]["accepted_count"] == 0
    assert by_source["Budi Auktioner"]["rejection_reasons"] == {
        "CLOTHING_RELEVANCE_MISSING": 1
    }
    assert by_source["PS Auction"]["accepted_count"] == 1

    assert se["coverage_health"]["productive_source_count"] == 1
    assert se["coverage_health"]["clothing_relevance_rejection_count"] == 1
    assert se["coverage_health"]["result_bearing_source_count"] == 2
    assert se["coverage_health"]["zero_result_source_count"] == 3

    assert de["coverage_health"]["accepted_signal_count"] == 0
    assert de["coverage_health"]["zero_result_source_count"] == 4
    assert de["coverage_health"]["diagnosis"] == "HEALTHY_ZERO_SIGNAL"
