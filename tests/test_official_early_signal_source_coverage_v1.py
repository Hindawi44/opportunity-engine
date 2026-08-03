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
    def __init__(
        self,
        responses: dict[
            object,
            list[dict[str, object]] | Exception,
        ],
    ) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def search(
        self,
        query: str,
        *,
        count: int,
        country: str,
        search_lang: str,
        freshness: str | None,
        use_cache: bool = True,
    ) -> list[dict[str, object]]:
        self.calls.append(
            {
                "query": query,
                "count": count,
                "country": country,
                "search_lang": search_lang,
                "freshness": freshness,
                "use_cache": use_cache,
            }
        )
        response = self.responses.get(
            (country, freshness),
            self.responses.get(country, []),
        )
        if isinstance(response, Exception):
            raise response
        return list(response)


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


def test_official_queries_retrieve_legal_events_before_clothing_filter() -> None:
    for spec in SOURCE_SPECS:
        folded = spec.query.casefold()
        assert any(term.casefold() in folded for term in spec.event_terms)
        assert not any(
            term.casefold() in folded for term in spec.clothing_terms
        )


def test_official_notice_becomes_signal_only_not_opportunity() -> None:
    spec = next(item for item in SOURCE_SPECS if item.market_code == "NO")
    client = FakeSearchClient(
        {
            "NO": [
                {
                    "title": "Konkurs: Nordic Workwear AS",
                    "url": (
                        "https://www.brreg.no/registersok/kunngjoringer/"
                        "nordic-workwear"
                    ),
                    "snippet": (
                        "Klesbutikk og arbeidstøy er tatt under "
                        "konkursbehandling."
                    ),
                    "extra_snippets": [],
                    "published_at": "2026-08-03T09:00:00Z",
                    "source_rank": 1,
                }
            ]
        }
    )
    report = collect_source_signals(client, spec, observed_at=NOW)
    signal = report["signals"][0]

    assert report["status"] == "SUCCESS"
    assert report["selected_freshness"] == "pd"
    assert len(report["freshness_attempts"]) == 1
    assert signal["signal_type"] == "INSOLVENCY_OR_LIQUIDATION"
    assert signal["company_name"] == "Nordic Workwear AS"
    assert signal["related_opportunity_id"] is None
    assert signal["metadata"]["signal_only"] is True
    assert signal["metadata"]["retrieval_freshness"] == "pd"
    assert signal["evidence"][0]["verified"] is False


def test_non_clothing_bankruptcy_is_valid_zero_after_retrieval() -> None:
    spec = next(item for item in SOURCE_SPECS if item.market_code == "SE")
    client = FakeSearchClient(
        {
            "SE": [
                {
                    "title": "Konkurs: Bygg & Betong AB",
                    "url": (
                        "https://poit.bolagsverket.se/poit/"
                        "PublicationDetails?id=1"
                    ),
                    "snippet": (
                        "Bolaget bedriver byggentreprenad och betongarbete."
                    ),
                    "extra_snippets": [],
                    "source_rank": 1,
                }
            ]
        }
    )
    report = collect_source_signals(client, spec, observed_at=NOW)

    assert report["status"] == "VALID_ZERO"
    assert report["result_count"] == 1
    assert report["signals"] == []
    assert report["rejected_result_count"] == 1
    assert len(client.calls) == 1


def test_unofficial_domain_is_rejected_even_when_keywords_match() -> None:
    spec = next(item for item in SOURCE_SPECS if item.market_code == "DE")
    client = FakeSearchClient(
        {
            "DE": [
                {
                    "title": "Insolvenz Modehaus Beispiel GmbH",
                    "url": "https://example.test/insolvenz/modehaus",
                    "snippet": (
                        "Bekleidung und Textilien im Insolvenzverfahren."
                    ),
                    "extra_snippets": [],
                    "source_rank": 1,
                }
            ]
        }
    )
    report = collect_source_signals(client, spec, observed_at=NOW)

    assert report["status"] == "VALID_ZERO"
    assert report["signals"] == []


def test_retrieval_zero_uses_day_week_month_fallback() -> None:
    spec = next(item for item in SOURCE_SPECS if item.market_code == "NO")
    client = FakeSearchClient(
        {
            ("NO", "pd"): [],
            ("NO", "pw"): [],
            ("NO", "pm"): [],
        }
    )
    report = collect_source_signals(client, spec, observed_at=NOW)

    assert report["status"] == "RETRIEVAL_ZERO"
    assert report["result_count"] == 0
    assert report["rejected_result_count"] == 0
    assert report["selected_freshness"] is None
    assert [item["freshness"] for item in report["freshness_attempts"]] == [
        "pd",
        "pw",
        "pm",
    ]
    assert [item["freshness"] for item in client.calls] == [
        "pd",
        "pw",
        "pm",
    ]


def test_week_fallback_stops_when_pages_are_retrieved() -> None:
    spec = next(item for item in SOURCE_SPECS if item.market_code == "SE")
    client = FakeSearchClient(
        {
            ("SE", "pd"): [],
            ("SE", "pw"): [
                {
                    "title": "Likvidation: Mode & Textil AB",
                    "url": (
                        "https://poit.bolagsverket.se/poit/"
                        "PublicationDetails?id=2"
                    ),
                    "snippet": "Klädbutik och textilbolag i likvidation.",
                    "extra_snippets": [],
                    "source_rank": 1,
                }
            ],
            ("SE", "pm"): [
                {
                    "title": "This result must not be requested",
                    "url": "https://poit.bolagsverket.se/unused",
                    "snippet": "konkurs kläder",
                    "extra_snippets": [],
                }
            ],
        }
    )
    report = collect_source_signals(client, spec, observed_at=NOW)

    assert report["status"] == "SUCCESS"
    assert report["selected_freshness"] == "pw"
    assert [item["freshness"] for item in client.calls] == ["pd", "pw"]
    assert report["accepted_signal_count"] == 1


def test_month_results_outside_clothing_are_valid_zero_not_retrieval_zero() -> None:
    spec = next(item for item in SOURCE_SPECS if item.market_code == "DE")
    client = FakeSearchClient(
        {
            ("DE", "pd"): [],
            ("DE", "pw"): [],
            ("DE", "pm"): [
                {
                    "title": "Insolvenz: Bauunternehmen Beispiel GmbH",
                    "url": (
                        "https://neu.insolvenzbekanntmachungen.de/"
                        "ap/details/456"
                    ),
                    "snippet": (
                        "Bauunternehmen im eröffneten Insolvenzverfahren."
                    ),
                    "extra_snippets": [],
                    "source_rank": 1,
                }
            ],
        }
    )
    report = collect_source_signals(client, spec, observed_at=NOW)

    assert report["status"] == "VALID_ZERO"
    assert report["selected_freshness"] == "pm"
    assert report["result_count"] == 1
    assert report["rejected_result_count"] == 1


def test_signal_identity_is_stable_and_duplicate_results_are_deduplicated() -> None:
    spec = next(item for item in SOURCE_SPECS if item.market_code == "DE")
    result = {
        "title": "Insolvenz: Modehaus Beispiel GmbH",
        "url": (
            "https://neu.insolvenzbekanntmachungen.de/"
            "ap/details/123#top"
        ),
        "snippet": (
            "Bekleidung und Textilien im eröffneten Insolvenzverfahren."
        ),
        "extra_snippets": [],
        "source_rank": 1,
    }
    client = FakeSearchClient({"DE": [result, dict(result)]})

    first = collect_source_signals(client, spec, observed_at=NOW)
    second = collect_source_signals(client, spec, observed_at=NOW)

    assert first["accepted_signal_count"] == 1
    assert (
        first["signals"][0]["signal_id"]
        == second["signals"][0]["signal_id"]
    )


def test_manifest_collection_writes_one_report_per_market(
    tmp_path: Path,
) -> None:
    client = FakeSearchClient(
        {
            "NO": [
                {
                    "title": "Konkurs: Nordic Workwear AS",
                    "url": (
                        "https://www.brreg.no/registersok/kunngjoringer/"
                        "nordic-workwear"
                    ),
                    "snippet": (
                        "Klesbutikk med arbeidstøy under konkursbehandling."
                    ),
                    "extra_snippets": [],
                    "source_rank": 1,
                }
            ],
            "SE": [
                {
                    "title": "Likvidation: Mode & Textil AB",
                    "url": (
                        "https://poit.bolagsverket.se/poit/"
                        "PublicationDetails?id=2"
                    ),
                    "snippet": "Klädbutik och textilbolag i likvidation.",
                    "extra_snippets": [],
                    "source_rank": 1,
                }
            ],
            "DE": [
                {
                    "title": "Insolvenz: Modehaus Beispiel GmbH",
                    "url": (
                        "https://neu.insolvenzbekanntmachungen.de/"
                        "ap/details/123"
                    ),
                    "snippet": (
                        "Bekleidung und Textilien im Insolvenzverfahren."
                    ),
                    "extra_snippets": [],
                    "source_rank": 1,
                }
            ],
        }
    )
    summary = collect_manifest_official_early_signals(
        _manifest(),
        root=tmp_path,
        client=client,
        observed_at=NOW,
    )

    assert summary["market_coverage"] == ["NO", "SE", "DE"]
    assert summary["status_counts"] == {"SUCCESS": 3}
    assert summary["signal_count"] == 3
    assert len(client.calls) == 3

    for relative in (
        "inputs/no-auksjonen/market-signal-report.json",
        "inputs/se-blinto/market-signal-report.json",
        "inputs/de-riegermann/market-signal-report.json",
    ):
        payload = json.loads(
            (tmp_path / relative).read_text(encoding="utf-8")
        )
        assert len(payload["signals"]) == 1
        assert payload["stored_signal_count"] == 1
        assert payload["automatic_contact"] is False
        assert payload["automatic_bid"] is False
        assert payload["automatic_purchase"] is False
        assert payload["automatic_payment"] is False


def test_missing_search_key_is_blocked_without_fabricating_signals(
    tmp_path: Path,
) -> None:
    def unavailable_client():
        raise ValueError("Set BRAVE_API_KEY or BRAVE_SEARCH_API_KEY")

    summary = collect_manifest_official_early_signals(
        _manifest(),
        root=tmp_path,
        client_factory=unavailable_client,
        observed_at=NOW,
    )

    assert summary["status_counts"] == {"BLOCKED": 3}
    assert summary["signal_count"] == 0
    assert all(item["signals"] == [] for item in summary["sources"])
