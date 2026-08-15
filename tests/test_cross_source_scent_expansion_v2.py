from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.discovery.cross_source_scent_entity_gated_v1 import (
    collect_entity_gated_cross_source_scent_expansion_v2,
)
from opportunity_engine.discovery.entity_scent_quality_gate_v1 import (
    ENGINE_VERSION as ENTITY_GATE_VERSION,
    build_entity_scent_quality_gate,
)
from opportunity_engine.discovery.search_provider import SearchHit


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_WORKFLOW = ROOT / ".github" / "workflows" / "multi-market-daily-operator-checkpoint.yaml"


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

    report = collect_entity_gated_cross_source_scent_expansion_v2(
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
        (signal.get("metadata") or {}).get("cross_source_stage") == "ENTITY_FOLLOW_UP"
        for signal in report["signals"]
    )
    assert report["entity_scent_quality_gate_version"] == ENTITY_GATE_VERSION
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

    report = collect_entity_gated_cross_source_scent_expansion_v2(
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

    report = collect_entity_gated_cross_source_scent_expansion_v2(
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, api_key, freshness: FakeProvider(market),
        max_requests=7,
    )

    assert report["requests_made"] == 7
    assert report["follow_up_request_count"] <= 1


def test_entity_gate_clusters_adenauer_and_filters_generic_pages() -> None:
    candidates = [
        {
            "market_code": "DE",
            "label": "Adenauer & Co.-Insolvenz",
            "score": 50,
            "source_url": "https://manager.example/adenauer",
            "source_title": "Adenauer & Co.-Insolvenz: Modemarke meldet Insolvenz",
            "parent_query_id": "de-cross-insolvency-stock",
        },
        {
            "market_code": "DE",
            "label": "Adenauer & Co insolvent",
            "score": 25,
            "source_url": "https://fashion.example/adenauer",
            "source_title": "Adenauer & Co insolvent: Modekette in Schwierigkeiten",
            "parent_query_id": "de-cross-administrator-fashion",
        },
        {
            "market_code": "DE",
            "label": "Modekette Adenauer & Co",
            "score": 50,
            "source_url": "https://news.example/adenauer",
            "source_title": "Modekette Adenauer & Co: Insolvenzverfahren eröffnet",
            "parent_query_id": "de-cross-insolvency-stock",
        },
        {
            "market_code": "DE",
            "label": "Restposten verkaufen",
            "score": 60,
            "source_url": "https://generic.example/restposten",
            "source_title": "Restposten verkaufen – Aufkäufer mit Vorauszahlung",
            "parent_query_id": "de-cross-liquidation-stock",
        },
        {
            "market_code": "DE",
            "label": "Ankauf von Marken-Schuhen als Restposten",
            "score": 75,
            "source_url": "https://generic.example/ankauf",
            "source_title": "Ankauf von Marken-Schuhen als Restposten – liquidato.de",
            "parent_query_id": "de-cross-liquidation-stock",
        },
    ]

    gate = build_entity_scent_quality_gate(candidates)

    assert gate["source_intelligence_count"] == 2
    assert gate["qualified_entity_count"] == 1
    adenauer = gate["qualified_entity_scents"][0]
    assert adenauer["label"] == "Adenauer & Co"
    assert adenauer["evidence_count"] == 3
    assert adenauer["independent_source_count"] == 3
    assert adenauer["score"] > 75
    assert adenauer["qualified_for_follow_up"] is True
    assert all(
        item.get("classification") == "SOURCE_INTELLIGENCE"
        for item in gate["source_intelligence"]
    )
    assert gate["promotion_to_opportunity_allowed"] is False


def test_v2_trial_is_wired_into_existing_checkpoint_without_sixth_workflow() -> None:
    text = CHECKPOINT_WORKFLOW.read_text(encoding="utf-8")
    assert "run_cross_source_scent_v2:" in text
    assert "cross_source_scent_v2_max_requests:" in text
    assert "Run optional cross-source scent expansion V2 trial" in text
    assert "scripts/run_cross_source_scent_expansion_v2.py" in text
    assert "tests/test_cross_source_scent_expansion_v2.py -q" in text
    assert not (ROOT / ".github" / "workflows" / "cross-source-scent-expansion-v2.yaml").exists()
