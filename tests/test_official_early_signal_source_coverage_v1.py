from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from opportunity_engine.discovery.official_early_signal_sources import (
    SOURCE_SPECS,
    collect_manifest_official_early_signals,
    collect_source_signals,
)


NOW = datetime(2026, 8, 3, 17, 0, tzinfo=timezone.utc)


class FakeSearchClient:
    def __init__(self, responses: dict[str, list[dict[str, object]]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def search(self, query: str, *, count: int, country: str, search_lang: str, freshness: str | None, use_cache: bool = True) -> list[dict[str, object]]:
        self.calls.append({"query": query, "count": count, "country": country, "search_lang": search_lang, "freshness": freshness, "use_cache": use_cache})
        return list(self.responses.get(country, []))


def _manifest() -> dict:
    return {
        "sources": [
            {"market_code": "NO", "source_name": "Auksjonen.no", "artifact_dir": "inputs/no-auksjonen"},
            {"market_code": "SE", "source_name": "Blinto", "artifact_dir": "inputs/se-blinto"},
            {"market_code": "DE", "source_name": "Riegermann", "artifact_dir": "inputs/de-riegermann"},
        ]
    }


def test_official_notice_becomes_signal_only_not_opportunity() -> None:
    spec = next(item for item in SOURCE_SPECS if item.market_code == "NO")
    client = FakeSearchClient({"NO": [{"title": "Konkurs: Nordic Workwear AS", "url": "https://www.brreg.no/registersok/kunngjoringer/nordic-workwear", "snippet": "Klesbutikk og arbeidstøy er tatt under konkursbehandling.", "extra_snippets": [], "published_at": "2026-08-03T09:00:00Z", "source_rank": 1}]})
    report = collect_source_signals(client, spec, observed_at=NOW)
    signal = report["signals"][0]
    assert report["status"] == "SUCCESS"
    assert signal["signal_type"] == "INSOLVENCY_OR_LIQUIDATION"
    assert signal["company_name"] == "Nordic Workwear AS"
    assert signal["related_opportunity_id"] is None
    assert signal["metadata"]["signal_only"] is True
    assert signal["evidence"][0]["verified"] is False


def test_non_clothing_bankruptcy_is_rejected() -> None:
    spec = next(item for item in SOURCE_SPECS if item.market_code == "SE")
    client = FakeSearchClient({"SE": [{"title": "Konkurs: Bygg & Betong AB", "url": "https://poit.bolagsverket.se/poit/PublicationDetails?id=1", "snippet": "Bolaget bedriver byggentreprenad och betongarbete.", "extra_snippets": [], "source_rank": 1}]})
    report = collect_source_signals(client, spec, observed_at=NOW)
    assert report["status"] == "VALID_ZERO"
    assert report["signals"] == []
    assert report["rejected_result_count"] == 1


def test_unofficial_domain_is_rejected_even_when_keywords_match() -> None:
    spec = next(item for item in SOURCE_SPECS if item.market_code == "DE")
    client = FakeSearchClient({"DE": [{"title": "Insolvenz Modehaus Beispiel GmbH", "url": "https://example.test/insolvenz/modehaus", "snippet": "Bekleidung und Textilien im Insolvenzverfahren.", "extra_snippets": [], "source_rank": 1}]})
    report = collect_source_signals(client, spec, observed_at=NOW)
    assert report["status"] == "VALID_ZERO"
    assert report["signals"] == []


def test_signal_identity_is_stable_and_duplicate_results_are_deduplicated() -> None:
    spec = next(item for item in SOURCE_SPECS if item.market_code == "DE")
    result = {"title": "Insolvenz: Modehaus Beispiel GmbH", "url": "https://neu.insolvenzbekanntmachungen.de/ap/details/123#top", "snippet": "Bekleidung und Textilien im eröffneten Insolvenzverfahren.", "extra_snippets": [], "source_rank": 1}
    client = FakeSearchClient({"DE": [result, dict(result)]})
    first = collect_source_signals(client, spec, observed_at=NOW)
    second = collect_source_signals(client, spec, observed_at=NOW)
    assert first["accepted_signal_count"] == 1
    assert first["signals"][0]["signal_id"] == second["signals"][0]["signal_id"]


def test_manifest_collection_writes_one_report_per_market(tmp_path: Path) -> None:
    client = FakeSearchClient({
        "NO": [{"title": "Konkurs: Nordic Workwear AS", "url": "https://www.brreg.no/registersok/kunngjoringer/nordic-workwear", "snippet": "Klesbutikk med arbeidstøy under konkursbehandling.", "extra_snippets": [], "source_rank": 1}],
        "SE": [{"title": "Likvidation: Mode & Textil AB", "url": "https://poit.bolagsverket.se/poit/PublicationDetails?id=2", "snippet": "Klädbutik och textilbolag i likvidation.", "extra_snippets": [], "source_rank": 1}],
        "DE": [{"title": "Insolvenz: Modehaus Beispiel GmbH", "url": "https://neu.insolvenzbekanntmachungen.de/ap/details/123", "snippet": "Bekleidung und Textilien im Insolvenzverfahren.", "extra_snippets": [], "source_rank": 1}],
    })
    summary = collect_manifest_official_early_signals(_manifest(), root=tmp_path, client=client, observed_at=NOW)
    assert summary["market_coverage"] == ["NO", "SE", "DE"]
    assert summary["status_counts"] == {"SUCCESS": 3}
    assert summary["signal_count"] == 3
    assert len(client.calls) == 3
    for relative in ("inputs/no-auksjonen/market-signal-report.json", "inputs/se-blinto/market-signal-report.json", "inputs/de-riegermann/market-signal-report.json"):
        payload = json.loads((tmp_path / relative).read_text(encoding="utf-8"))
        assert len(payload["signals"]) == 1
        assert payload["automatic_contact"] is False
        assert payload["automatic_bid"] is False
        assert payload["automatic_purchase"] is False
        assert payload["automatic_payment"] is False


def test_missing_search_key_is_blocked_without_fabricating_signals(tmp_path: Path) -> None:
    def unavailable_client():
        raise ValueError("Set BRAVE_API_KEY or BRAVE_SEARCH_API_KEY")
    summary = collect_manifest_official_early_signals(_manifest(), root=tmp_path, client_factory=unavailable_client, observed_at=NOW)
    assert summary["status_counts"] == {"BLOCKED": 3}
    assert summary["signal_count"] == 0
    assert all(item["signals"] == [] for item in summary["sources"])
