from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Sequence

from opportunity_engine.discovery.bridal_english_market_search import (
    ENGLISH_BRIDAL_QUERIES,
    ENGLISH_SEARCH_LANE,
    _ORIGINAL_LOCAL_COLLECTOR,
    english_bridal_signal_from_hit,
)
from opportunity_engine.discovery.bridal_liquidation_feed import (
    ADAPTIVE_MARKETS,
    BRIDAL_QUERIES,
    BRIDAL_QUERY_PACKS,
    FEED_FAMILY,
    SUPPORTED_MARKETS,
    bridal_signal_from_hit,
    collect_manifest_bridal_liquidation_signals,
)
from opportunity_engine.discovery.search_provider import SearchHit


NOW = datetime(2026, 8, 5, 20, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts/build_domain_market_intelligence_feed.py"
DISCOVERY_INIT = ROOT / "src/opportunity_engine/discovery/__init__.py"


def _manifest() -> dict:
    return {
        "sources": [
            {"market_code": "NO", "artifact_dir": "artifacts/no"},
            {"market_code": "SE", "artifact_dir": "artifacts/se"},
            {"market_code": "DE", "artifact_dir": "artifacts/de"},
        ]
    }


def test_feed_has_local_and_english_queries_for_each_existing_market() -> None:
    assert tuple(BRIDAL_QUERIES) == SUPPORTED_MARKETS == ("NO", "SE", "DE")
    assert tuple(ENGLISH_BRIDAL_QUERIES) == SUPPORTED_MARKETS
    assert len(BRIDAL_QUERIES) == len(ENGLISH_BRIDAL_QUERIES) == 3
    assert "brudekjoler" in BRIDAL_QUERIES["NO"].query
    assert "brudklänningar" in BRIDAL_QUERIES["SE"].query
    assert "Brautkleider" in BRIDAL_QUERIES["DE"].query
    assert "Norway" in ENGLISH_BRIDAL_QUERIES["NO"].query
    assert "Sweden" in ENGLISH_BRIDAL_QUERIES["SE"].query
    assert "Germany" in ENGLISH_BRIDAL_QUERIES["DE"].query
    assert all(
        query.language == "en" and query.lane == ENGLISH_SEARCH_LANE
        for query in ENGLISH_BRIDAL_QUERIES.values()
    )


def test_se_de_query_packs_cover_separate_commercial_intents() -> None:
    assert ADAPTIVE_MARKETS == frozenset({"SE", "DE"})
    assert len(BRIDAL_QUERY_PACKS["NO"]) == 1
    assert len(BRIDAL_QUERY_PACKS["SE"]) == 5
    assert len(BRIDAL_QUERY_PACKS["DE"]) == 5
    for market in ("SE", "DE"):
        assert [query.intent for query in BRIDAL_QUERY_PACKS[market]] == [
            "LIQUIDATION",
            "SAMPLE_STOCK",
            "STOCKLOT_WHOLESALE",
            "AUCTION",
            "CLOSURE_STOCK",
        ]
        assert BRIDAL_QUERY_PACKS[market][0].phase == "CORE"
        assert all(query.phase == "ADAPTIVE" for query in BRIDAL_QUERY_PACKS[market][1:])


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


def test_rejects_one_private_used_wedding_dress_in_local_language() -> None:
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


def test_accepts_english_commercial_bridal_market_signal() -> None:
    signal = english_bridal_signal_from_hit(
        SearchHit(
            title="Bridal boutique closing down – 60 wedding dresses",
            url="https://example.no/english-bridal-closeout?utm_campaign=test",
            description=(
                "Full bridal inventory and sample wedding dresses offered in a "
                "stock clearance in Norway."
            ),
            provider="Brave Search",
        ),
        market_code="NO",
        query=ENGLISH_BRIDAL_QUERIES["NO"],
        observed_at=NOW,
    )

    assert signal is not None
    assert signal.signal_type.value == "BUSINESS_CLOSURE"
    assert signal.metadata["search_language"] == "en"
    assert signal.metadata["search_lane"] == ENGLISH_SEARCH_LANE
    assert signal.metadata["inventory_domain"] == "BRIDAL"
    assert signal.metadata["promotion_to_opportunity_allowed"] is False
    assert str(signal.source_url) == "https://example.no/english-bridal-closeout"


def test_rejects_one_private_wedding_dress_in_english() -> None:
    signal = english_bridal_signal_from_hit(
        SearchHit(
            title="My wedding dress for sale",
            url="https://example.no/my-dress",
            description="One used wedding dress, size 38, sold by a private person.",
            provider="Brave Search",
        ),
        market_code="NO",
        query=ENGLISH_BRIDAL_QUERIES["NO"],
        observed_at=NOW,
    )

    assert signal is None


_LOCAL_FIXTURES = {
    "NO": SearchHit(
        title="Brudesalong opphørssalg med brudekjoler",
        url="https://example.no/closing",
        description="Varelager og prøvekjoler selges samlet.",
        provider="Fake Brave",
    ),
    "SE": SearchHit(
        title="Brudbutik konkurs – brudklänningar och lager säljes",
        url="https://example.se/konkurs",
        description="Hela varulagret med provklänningar säljes.",
        provider="Fake Brave",
    ),
    "DE": SearchHit(
        title="Brautmodengeschäft Insolvenz – Brautkleider Restposten",
        url="https://example.de/insolvenz",
        description="Lagerverkauf der Musterkleider und Kollektion.",
        provider="Fake Brave",
    ),
}
_ENGLISH_FIXTURES = {
    "NO": SearchHit(
        title="Norway bridal shop closing down – wedding dresses",
        url="https://example.no/english-closing",
        description="Bridal inventory and sample wedding dresses in a closing sale.",
        provider="Fake Brave",
    ),
    "SE": SearchHit(
        title="Sweden bridal boutique liquidation – wedding dresses",
        url="https://example.se/english-liquidation",
        description="Full bridal stock and sample bridal gowns in liquidation.",
        provider="Fake Brave",
    ),
    "DE": SearchHit(
        title="Germany bridal store stock clearance – wedding dresses",
        url="https://example.de/english-clearance",
        description="Bridal inventory lot and sample wedding dresses in stock clearance.",
        provider="Fake Brave",
    ),
}


class FakeProvider:
    def __init__(self, market_code: str) -> None:
        self.market_code = market_code
        self.calls: list[tuple[str, int]] = []

    @property
    def name(self) -> str:
        return "Fake Brave"

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        self.calls.append((query, count))
        if "bridal shop liquidation" in query:
            return [_ENGLISH_FIXTURES[self.market_code]]
        return [_LOCAL_FIXTURES[self.market_code]]


def test_collection_is_bounded_to_fourteen_requests_and_flows_into_market_reports(
    tmp_path: Path,
) -> None:
    providers: dict[str, list[FakeProvider]] = {market: [] for market in SUPPORTED_MARKETS}

    def factory(market_code: str, api_key: str, freshness: str | None) -> FakeProvider:
        assert api_key == "secret"
        assert freshness == "py"
        provider = FakeProvider(market_code)
        providers[market_code].append(provider)
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
    assert report["search_languages"] == ["local-market-language", "en"]
    assert report["english_market_search_enabled"] is True
    assert report["query_budget_total"] == 14
    assert report["requests_made"] == 14
    assert report["local_requests_made"] == 11
    assert report["english_requests_made"] == 3
    assert report["signal_count"] == 6
    assert report["local_signal_count"] == 3
    assert report["english_signal_count"] == 3
    assert report["private_single_dress_listings_rejected"] is True
    assert report["automatic_purchase"] is False

    assert [len(provider.calls) for provider in providers["NO"]] == [1, 1]
    assert [len(provider.calls) for provider in providers["SE"]] == [5, 1]
    assert [len(provider.calls) for provider in providers["DE"]] == [5, 1]

    local_sources = {
        source["source_country"]: source
        for source in report["local_language_report"]["sources"]
    }
    assert local_sources["NO"]["adaptive_expansion_eligible"] is False
    for market in ("SE", "DE"):
        assert local_sources[market]["adaptive_expansion_triggered"] is True
        assert local_sources[market]["adaptive_stop_reason"] == "QUERY_PACK_EXHAUSTED"
        assert local_sources[market]["queries_attempted"] == 5
        assert local_sources[market]["distinct_domain_count"] == 1

    for market in ("no", "se", "de"):
        path = tmp_path / "artifacts" / market / "market-signal-report.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["signal_count"] == 2
        assert all(
            signal["metadata"]["inventory_domain"] == "BRIDAL"
            for signal in payload["signals"]
        )
        assert any(
            signal["metadata"].get("search_language") == "en"
            for signal in payload["signals"]
        )


class DiversifyingLocalProvider:
    def __init__(self, market_code: str) -> None:
        self.market_code = market_code
        self.calls: list[tuple[str, int]] = []

    @property
    def name(self) -> str:
        return "Diversifying Fake Brave"

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        self.calls.append((query, count))
        if len(self.calls) == 1:
            return [_LOCAL_FIXTURES[self.market_code]]
        if self.market_code == "SE":
            return [
                SearchHit(
                    title="Brudbutik lagerförsäljning – provklänningar",
                    url="https://second-bridal.se/lager",
                    description="Varulager med butiksexemplar säljes efter utförsäljning.",
                    provider=self.name,
                )
            ]
        if self.market_code == "DE":
            return [
                SearchHit(
                    title="Brautladen Musterverkauf – Musterkleider",
                    url="https://zweite-brautquelle.de/musterverkauf",
                    description="Warenbestand mit Ausstellungsstücke im Abverkauf.",
                    provider=self.name,
                )
            ]
        return []


def test_adaptive_depth_stops_after_two_signals_from_two_domains(tmp_path: Path) -> None:
    providers: dict[str, DiversifyingLocalProvider] = {}

    def factory(
        market_code: str,
        api_key: str,
        freshness: str | None,
    ) -> DiversifyingLocalProvider:
        provider = DiversifyingLocalProvider(market_code)
        providers[market_code] = provider
        return provider

    report = _ORIGINAL_LOCAL_COLLECTOR(
        _manifest(),
        root=tmp_path,
        observed_at=NOW,
        environment={"BRAVE_SEARCH_API_KEY": "secret"},
        provider_factory=factory,
        results_per_query=8,
    )

    assert report["query_budget_total"] == 11
    assert report["requests_made"] == 5
    by_market = {source["source_country"]: source for source in report["sources"]}
    assert by_market["NO"]["queries_attempted"] == 1
    for market in ("SE", "DE"):
        source = by_market[market]
        assert source["accepted_signal_count"] == 2
        assert source["distinct_domain_count"] == 2
        assert source["adaptive_expansion_triggered"] is True
        assert source["adaptive_stop_reason"] == "EVIDENCE_DIVERSIFIED"
        assert source["queries_attempted"] == 2
        assert len(providers[market].calls) == 2


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
    assert report["query_budget_total"] == 14
    assert report["status_counts"] == {"BLOCKED_CONFIGURATION": 3}
    assert all(
        source["local_language_status"] == "BLOCKED_CONFIGURATION"
        and source["english_language_status"] == "BLOCKED_CONFIGURATION"
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


def test_daily_builder_uses_existing_feed_and_package_installs_english_lane() -> None:
    builder_text = BUILD_SCRIPT.read_text(encoding="utf-8")
    init_text = DISCOVERY_INIT.read_text(encoding="utf-8")
    assert "collect_manifest_bridal_liquidation_signals" in builder_text
    assert 'bridal-liquidation-feed.json' in builder_text
    assert 'brief["bridal_liquidation_feed"]' in builder_text
    assert '"private_single_dress_listings_rejected"' in builder_text
    assert '"promotion_to_opportunity_allowed": False' in builder_text
    assert "install_bilingual_bridal_search" in init_text
    assert collect_manifest_bridal_liquidation_signals.__module__.endswith(
        "bridal_english_market_search"
    )
