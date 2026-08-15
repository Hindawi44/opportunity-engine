from __future__ import annotations

from pathlib import Path

from opportunity_engine.discovery.se_de_source_coverage_gap import (
    COVERAGE_HEALTH_VERSION,
    collect_manifest_se_de_source_coverage_gap,
)


def _manifest() -> dict:
    return {
        "sources": [
            {"market_code": "SE", "artifact_dir": "inputs/se-blinto"},
            {"market_code": "DE", "artifact_dir": "inputs/de-riegermann"},
        ]
    }


def _prepare(tmp_path: Path) -> None:
    (tmp_path / "inputs/se-blinto").mkdir(parents=True)
    (tmp_path / "inputs/de-riegermann").mkdir(parents=True)


def test_coverage_health_distinguishes_healthy_zero_from_retrieval_gap(tmp_path: Path) -> None:
    _prepare(tmp_path)

    class Provider:
        def __init__(self, market: str) -> None:
            self.market = market
            self.calls = 0

        def search(self, query: str, *, count: int = 10):
            self.calls += 1
            if self.market == "DE" and self.calls > 1:
                raise RuntimeError("simulated provider failure")
            return []

    report = collect_manifest_se_de_source_coverage_gap(
        _manifest(),
        root=tmp_path,
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, api_key, freshness: Provider(market),
    )

    assert report["coverage_health_version"] == COVERAGE_HEALTH_VERSION
    se = report["coverage_health"]["SE"]
    de = report["coverage_health"]["DE"]

    assert se["query_budget"] == 5
    assert se["queries_succeeded"] == 5
    assert se["retrieval_rate"] == 1.0
    assert se["accepted_signal_count"] == 0
    assert se["diagnosis"] == "HEALTHY_ZERO_SIGNAL"
    assert se["direct_sale_or_auction_source_count"] == 4
    assert se["early_insolvency_source_count"] == 1

    assert de["query_budget"] == 4
    assert de["queries_succeeded"] == 1
    assert de["retrieval_rate"] == 0.25
    assert de["diagnosis"] == "RETRIEVAL_GAP"
    assert de["direct_sale_or_auction_source_count"] == 3
    assert de["early_insolvency_source_count"] == 1


def test_coverage_health_reports_blocked_when_api_key_missing(tmp_path: Path) -> None:
    _prepare(tmp_path)
    report = collect_manifest_se_de_source_coverage_gap(
        _manifest(),
        root=tmp_path,
        environment={},
    )

    assert report["requests_made"] == 0
    assert report["coverage_health"]["SE"]["diagnosis"] == "RETRIEVAL_BLOCKED"
    assert report["coverage_health"]["DE"]["diagnosis"] == "RETRIEVAL_BLOCKED"
