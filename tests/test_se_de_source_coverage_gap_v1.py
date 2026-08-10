from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.se_de_source_coverage_gap import (
    SOURCE_QUERIES,
    collect_manifest_se_de_source_coverage_gap,
)


ROOT = Path(__file__).resolve().parents[1]
DAILY = ROOT / "scripts" / "build_domain_market_intelligence_feed.py"


def _manifest() -> dict:
    return {
        "sources": [
            {
                "market_code": "NO",
                "source_name": "Auksjonen.no",
                "artifact_dir": "inputs/no-auksjonen",
            },
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


def test_source_gap_queries_are_explicitly_bounded_to_se_de_sources() -> None:
    assert tuple(SOURCE_QUERIES) == ("SE", "DE")
    assert [item.source_name for item in SOURCE_QUERIES["SE"]] == [
        "Budi Auktioner",
        "Kronofogden Webauktion",
    ]
    assert [item.source_name for item in SOURCE_QUERIES["DE"]] == [
        "HTKG Online-Versteigerungen",
        "Sen & Sen",
    ]
    assert sum(len(items) for items in SOURCE_QUERIES.values()) == 4
    assert all("site:" in item.query for items in SOURCE_QUERIES.values() for item in items)


def test_source_gap_radar_merges_four_strict_signals_before_core(tmp_path: Path) -> None:
    for relative in ("inputs/se-blinto", "inputs/de-riegermann"):
        (tmp_path / relative).mkdir(parents=True)

    calls: list[tuple[str, str, int]] = []

    class FakeProvider:
        name = "Fake Brave"

        def __init__(self, market_code: str) -> None:
            self.market_code = market_code

        def search(self, query: str, *, count: int = 10):
            calls.append((self.market_code, query, count))
            if "site:budi.se" in query:
                return [
                    SearchHit(
                        title="Kläder säljes via konkursauktion",
                        url="https://www.budi.se/objekt/200001/klader/klader-fran-konkurs",
                        description="Parti kläder och skor från företag som gått i konkurs.",
                        provider="Brave Search",
                    )
                ]
            if "site:auktion.kronofogden.se" in query:
                return [
                    SearchHit(
                        title="Kläder & Skor - Webauktion",
                        url="https://auktion.kronofogden.se/auk/w.ObjectList?inCategoryId=1&utm_source=x",
                        description="Varuparti och konkurslager med kläder säljs på auktion.",
                        provider="Brave Search",
                    )
                ]
            if "site:online-versteigerungen.ht-kg.de" in query:
                return [
                    SearchHit(
                        title="Online-Insolvenzversteigerung ETERNA Mode GmbH",
                        url="https://online-versteigerungen.ht-kg.de/de/Auktionen/Mode/123",
                        description="Warenbestand aus Bekleidung und Textilien wird versteigert.",
                        provider="Brave Search",
                    )
                ]
            return [
                SearchHit(
                    title="Textil-Warenbestand, Freizeit- und Arbeitskleidung",
                    url="https://www.sen-sen.de/php/t9999-Textil-Warenbestand",
                    description="Liquidationsverkauf aus Insolvenz mit Bekleidung und Textil.",
                    provider="Brave Search",
                )
            ]

    report = collect_manifest_se_de_source_coverage_gap(
        _manifest(),
        root=tmp_path,
        observed_at=datetime(2026, 8, 10, 8, 0, tzinfo=timezone.utc),
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, api_key, freshness: FakeProvider(market),
    )

    assert report["feed_family"] == "SE_DE_SOURCE_COVERAGE_GAP_V1"
    assert report["market_coverage"] == ["SE", "DE"]
    assert report["query_budget_total"] == 4
    assert report["requests_made"] == 4
    assert len(calls) == 4
    assert all(count == 8 for _, _, count in calls)
    assert report["signal_count"] == 4
    assert report["status_counts"] == {"SUCCESS": 2}
    assert report["promotion_to_opportunity_allowed"] is False
    assert report["top5_eligible"] is False
    assert report["automatic_contact"] is False
    assert report["automatic_bid"] is False
    assert report["automatic_purchase"] is False
    assert report["automatic_payment"] is False

    by_market = {item["source_country"]: item for item in report["sources"]}
    assert by_market["SE"]["accepted_signal_count"] == 2
    assert by_market["DE"]["accepted_signal_count"] == 2

    source_names = {
        signal["metadata"]["coverage_gap_source_name"]
        for source in report["sources"]
        for signal in source["signals"]
    }
    assert source_names == {
        "Budi Auktioner",
        "Kronofogden Webauktion",
        "HTKG Online-Versteigerungen",
        "Sen & Sen",
    }

    se_stored = json.loads(
        (tmp_path / "inputs/se-blinto/market-signal-report.json").read_text(
            encoding="utf-8"
        )
    )
    de_stored = json.loads(
        (tmp_path / "inputs/de-riegermann/market-signal-report.json").read_text(
            encoding="utf-8"
        )
    )
    assert se_stored["signal_count"] == 2
    assert de_stored["signal_count"] == 2
    assert not (tmp_path / "inputs/no-auksjonen/market-signal-report.json").exists()


def test_source_gap_rejects_result_outside_approved_source_domain(tmp_path: Path) -> None:
    for relative in ("inputs/se-blinto", "inputs/de-riegermann"):
        (tmp_path / relative).mkdir(parents=True)

    class FakeProvider:
        name = "Fake Brave"

        def __init__(self, market_code: str) -> None:
            self.market_code = market_code

        def search(self, query: str, *, count: int = 10):
            if "site:budi.se" in query:
                return [
                    SearchHit(
                        title="Kläder från konkursauktion",
                        url="https://unapproved.example.se/auction/1",
                        description="Parti kläder från konkurs.",
                        provider="Brave Search",
                    )
                ]
            return []

    report = collect_manifest_se_de_source_coverage_gap(
        _manifest(),
        root=tmp_path,
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, api_key, freshness: FakeProvider(market),
    )

    assert report["requests_made"] == 4
    assert report["signal_count"] == 0
    assert report["status_counts"] == {"VALID_ZERO": 2}
    assert report["sources"][0]["rejected_result_count"] == 1


def test_daily_wrapper_runs_source_gap_before_existing_core_and_surfaces_it() -> None:
    text = DAILY.read_text(encoding="utf-8")
    main_block = text[text.index("def main() -> int:") :]

    assert "collect_manifest_se_de_source_coverage_gap" in text
    assert "se-de-source-coverage-gap.json" in text
    assert 'brief["se_de_source_coverage_gap"]' in text
    assert main_block.index("_run_se_de_source_gap_pre_core") < main_block.index(
        "_load_core_module().main()"
    )
    assert "Budi Auktioner" in text
    assert "Kronofogden Webauktion" in text
    assert "HTKG Online-Versteigerungen" in text
    assert "Sen & Sen" in text
