from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.discovery.cross_source_scent_expansion_v2 import (
    collect_cross_source_scent_expansion_v2,
)
from opportunity_engine.discovery.search_provider import SearchHit


def test_cross_source_discovers_and_follows_company_scent() -> None:
    calls: list[tuple[str, str]] = []

    class FakeProvider:
        name = "Fake Brave"

        def __init__(self, market: str) -> None:
            self.market = market

        def search(self, query: str, *, count: int = 10):
            calls.append((self.market, query))
            if self.market == "DE" and "Insolvenzverfahren" in query and '"Adenauer Mode GmbH"' not in query:
                return [
                    SearchHit(
                        title="Insolvenz Adenauer Mode GmbH - Warenbestand soll verwertet werden",
                        url="https://example.de/news/adenauer-mode-insolvenz",
                        description="Das Modehaus Adenauer Mode GmbH ist insolvent. Bekleidung und Warenbestand sollen verkauft werden.",
                        provider="Brave Search",
                    )
                ]
            if self.market == "DE" and '"Adenauer Mode GmbH"' in query:
                return [
                    SearchHit(
                        title="Adenauer Mode GmbH - Insolvenzauktion mit Bekleidung",
                        url="https://auction.example.de/adenauer-mode",
                        description="Warenbestand mit Mode und Bekleidung wird versteigert.",
                        provider="Brave Search",
                    )
                ]
            return []

    report = collect_cross_source_scent_expansion_v2(
        observed_at=datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc),
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, api_key, freshness: FakeProvider(market),
        max_requests=12,
    )

    assert report["status"] == "SUCCESS"
    assert report["requests_made"] <= 12
    assert report["strong_scent_count"] >= 1
    assert report["followed_scent_count"] >= 1
    assert any(item["label"] == "Adenauer Mode GmbH" for item in report["followed_scents"])
    assert report["accepted_signal_count"] >= 2
    assert any(
        (signal.get("metadata") or {}).get("cross_source_stage") == "FOLLOW_UP"
        for signal in report["signals"]
    )
    assert report["promotion_to_opportunity_allowed"] is False
    assert report["top5_eligible"] is False
    assert report["automatic_purchase"] is False


def test_cross_source_rejects_restaurant_noise() -> None:
    class FakeProvider:
        name = "Fake Brave"

        def search(self, query: str, *, count: int = 10):
            if "konkurs" in query.casefold():
                return [
                    SearchHit(
                        title="Restaurang i konkurs - köksutrustning säljs",
                        url="https://example.se/restaurang-konkurs",
                        description="Restaurangutrustning, maskiner och kök från konkurs.",
                        provider="Brave Search",
                    )
                ]
            return []

    report = collect_cross_source_scent_expansion_v2(
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, api_key, freshness: FakeProvider(),
        max_requests=6,
    )

    assert report["accepted_signal_count"] == 0
    assert report["strong_scent_count"] == 0
    assert report["followed_scent_count"] == 0
    assert report["requests_made"] == 6


def test_cross_source_budget_is_hard_bounded() -> None:
    class FakeProvider:
        name = "Fake Brave"

        def __init__(self, market: str) -> None:
            self.market = market

        def search(self, query: str, *, count: int = 10):
            if '"' in query:
                return []
            company = "Modehaus Beispiel GmbH" if self.market == "DE" else "Exempel Mode AB"
            return [
                SearchHit(
                    title=f"Konkurs Insolvenz {company} - varulager Warenbestand mode bekleidung",
                    url=f"https://{self.market.lower()}.example/{abs(hash(query))}",
                    description="Mode Bekleidung kläder konkurs Insolvenz Warenbestand varulager auktion.",
                    provider="Brave Search",
                )
            ]

    report = collect_cross_source_scent_expansion_v2(
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, api_key, freshness: FakeProvider(market),
        max_requests=7,
    )

    assert report["requests_made"] == 7
    assert report["follow_up_request_count"] <= 1
