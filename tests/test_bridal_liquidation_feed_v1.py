from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Sequence

from opportunity_engine.discovery.bridal_liquidation_feed import (
    BRIDAL_QUERIES,
    FEED_FAMILY,
    SUPPORTED_MARKETS,
    bridal_signal_from_hit,
    collect_manifest_bridal_liquidation_signals,
)
from opportunity_engine.discovery.search_provider import SearchHit


NOW = datetime(2026, 8, 5, 20, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts/build_domain_market_intelligence_feed.py"


def _manifest() -> dict:
    return {
        "sources": [
            {"market_code": "NO", "artifact_dir": "artifacts/no"},
            {"market_code": "SE", "artifact_dir": "artifacts/se"},
            {"market_code": "DE", "artifact_dir": "artifacts/de"},
        ]
    }


def test_feed_has_one_bounded_query_for_each_existing_market() -> None:
    assert tuple(BRIDAL_QUERIES) == SUPPORTED_MARKETS == ("NO", "SE", "DE")
    assert len(BRIDAL_QUERIES) == 3
    assert "brudekjoler" in BRIDAL_QUERIES["NO"].query
    assert "brudklänningar" in BRIDAL_QUERIES["SE"].query
    assert "Brautkleider" in BRIDAL_QUERIES["DE"].query


def test_accepts_commercial_norwegian_bridal_liquidation_signal() -> None:
    signal = bridal_signal_from_hit(
        SearchHit(
            title="Brudesalong avvikles – 40 brudekjoler og varelager selges",
            url="https://example.no/bridal-stock?utm_source=test",
            description="Hele butikkens prøvekjoler og restlager selges etter opphørssalg.",
            provider="Brave Search",
        ),
        market_code="NO",
        query=BRIDAL_QUERIES["NO"],
        observed_at=NOW,
    )

    assert signal is not None
    assert signal.signal_type.value == "BUSINESS_CLOSURE"
    assert signal.source_country == "NO"
    assert signal.metadata["inventory_domain"] == "BRIDAL"
    assert signal.metadata["commercial_batch_gate"] is True
    assert signal.metadata["promotion_to_opportunity_allowed"] is False
    assert str(signal.source_url) == "https://example.no/bridal-stock"


def test_rejects_one_private_used_wedding_dress() -> None:
    signal = bridal_signal_from_hit(
        SearchHit(
            title="Min brukte brudekjole selges",
            url="https://example.no/private-dress",
            description="Én kjole i størrelse 38 fra privatperson.",
            provider="Brave Search",
        ),
        market_code="NO",
        query=BRIDAL_QUERIES["NO"],
        observed_at=NOW,
    )

    assert signal is None


def test_accepts_german_sample_dress_stock_clearance() -> None:
    signal = bridal_signal_from_hit(
        SearchHit(
            title="Brautladen Lagerverkauf – Musterkleider und Brautkleider",
            url="https://example.de/lagerverkauf",
            description="Restposten einer Brautkollektion nach Geschäftsauflösung.",
            provider="Brave Search",
        ),
        market_code="DE",
        query=BRIDAL_QUERIES["DE"],
        observed_at=NOW,
    )

    assert signal is not None
    assert signal.signal_type.value == "BUSINESS_CLOSURE"
    assert signal.metadata["feed_family"] == FEED_FAMILY
    assert signal.status.value == "WATCH"


class FakeProvider:
    def __init__(self, market_code: str) -> None:
        self.market_code = market_code
        self.calls: list[tuple[str, int]] = []

    @property
    def name(self) -> str:
        return "Fake Brave"

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        self.calls.append((query, count))
        fixtures = {
            "NO": SearchHit(
                title="Brudesalong opphørssalg med brudekjoler",
                url="https://example.no/closing",
                description="Varelager og prøvekjoler selges samlet.",
                provider=self.name,
            ),
            "SE": SearchHit(
                title="Brudbutik konkurs – brudklänningar och lager säljes",
                url="https://example.se/konkurs",
                description="Hela varulagret med provklänningar säljes.",
                provider=self.name,
            ),
            "DE": SearchHit(
                title="Brautmodengeschäft Insolvenz – Brautkleider Restposten",
                url="https://example.de/insolvenz",
                description="Lagerverkauf der Musterkleider und Kollektion.",
                provider=self.name,
            ),
        }
        return [fixtures[self.market_code]]


def test_collection_is_bounded_to_three_requests_and_flows_into_market_reports(
    tmp_path: Path,
) -> None:
    providers: dict[str, FakeProvider] = {}

    def factory(market_code: str, api_key: str, freshness: str | None) -> FakeProvider:
        assert api_key == "secret"
        assert freshness == "py"
        provider = FakeProvider(market_code)
        providers[market_code] = provider
        return provider

    report = collect_manifest_bridal_liquidation_signals(
        _manifest(),
        root=tmp_path,
        observed_at=NOW,
        environment={"BRAVE_SEARCH_API_KEY": "secret"},
        provider_factory=factory,
        results_per_query=8,
    )

    assert report["status_counts"] == {"SUCCESS": 3}
    assert report["query_budget_total"] == 3
    assert report["requests_made"] == 3
    assert report["signal_count"] == 3
    assert report["private_single_dress_listings_rejected"] is True
    assert report["automatic_purchase"] is False
    assert all(len(provider.calls) == 1 for provider in providers.values())

    for market in ("no", "se", "de"):
        path = tmp_path / "artifacts" / market / "market-signal-report.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["signal_count"] == 1
        assert payload["signals"][0]["metadata"]["inventory_domain"] == "BRIDAL"


def test_missing_brave_key_is_explicit_and_makes_no_request() -> None:
    def forbidden_factory(*args, **kwargs):
        raise AssertionError("provider must not be initialized")

    report = collect_manifest_bridal_liquidation_signals(
        _manifest(),
        observed_at=NOW,
        environment={},
        provider_factory=forbidden_factory,
    )

    assert report["requests_made"] == 0
    assert report["signal_count"] == 0
    assert report["status_counts"] == {"BLOCKED_CONFIGURATION": 3}
    assert all(
        source["block_reason"] == "BRAVE_SEARCH_API_KEY_MISSING"
        for source in report["sources"]
    )


def test_invalid_results_limit_is_rejected() -> None:
    try:
        collect_manifest_bridal_liquidation_signals(
            _manifest(),
            observed_at=NOW,
            environment={},
            results_per_query=11,
        )
    except ValueError as exc:
        assert "results_per_query" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("expected ValueError")


def test_daily_builder_runs_and_exposes_the_bridal_tributary() -> None:
    text = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert "collect_manifest_bridal_liquidation_signals" in text
    assert 'bridal-liquidation-feed.json' in text
    assert 'brief["bridal_liquidation_feed"]' in text
    assert '"private_single_dress_listings_rejected"' in text
    assert '"promotion_to_opportunity_allowed": False' in text
