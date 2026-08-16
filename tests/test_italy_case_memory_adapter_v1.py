from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.discovery.italy_case_memory_adapter import (
    ENGINE_VERSION,
    adapt_italy_signal_to_entity_memory,
    build_italy_case_memory_adapter,
    run_italy_case_memory_cycle,
)
from opportunity_engine.discovery.italy_market_discovery import (
    ITALY_DISCOVERY_QUERIES,
    italy_signal_from_hit,
)
from opportunity_engine.discovery.search_provider import SearchHit


DAY_1 = datetime(2026, 8, 16, 10, 0, tzinfo=timezone.utc)
DAY_2 = datetime(2026, 8, 17, 10, 0, tzinfo=timezone.utc)


def _insolvency_signal(*, observed_at: datetime, url: str, title: str) -> dict:
    query = next(
        item
        for item in ITALY_DISCOVERY_QUERIES
        if item.intent == "INSOLVENCY_LIQUIDATION"
    )
    signal = italy_signal_from_hit(
        SearchHit(
            title=title,
            url=url,
            description=(
                "Impresa di abbigliamento in liquidazione giudiziale. "
                "La procedura riguarda il settore moda e tessile."
            ),
            provider="Fake Brave",
        ),
        query=query,
        rank=1,
        observed_at=observed_at,
    )
    assert signal is not None
    return signal.model_dump(mode="json")


def _aurora_signal(*, observed_at: datetime, url: str) -> dict:
    return _insolvency_signal(
        observed_at=observed_at,
        url=url,
        title="Liquidazione giudiziale di Aurora Moda S.r.l.",
    )


def test_adapter_requires_a_concrete_italian_company_identity() -> None:
    concrete = _aurora_signal(
        observed_at=DAY_1,
        url="https://news.example.it/aurora-liquidazione",
    )
    adapted, reason = adapt_italy_signal_to_entity_memory(concrete)

    assert reason is None
    assert adapted is not None
    assert adapted["company_name"] == "Aurora Moda S.r.l"
    assert adapted["metadata"]["entity_scent_classification"] == "ENTITY_SCENT"
    assert adapted["metadata"]["entity_scent_quality_gate"] == ENGINE_VERSION
    assert adapted["metadata"]["entity_key"] == "aurora moda"
    assert adapted["metadata"]["entity_label"] == "Aurora Moda S.r.l"
    assert adapted["metadata"]["promotion_to_opportunity_allowed"] is False

    generic = _insolvency_signal(
        observed_at=DAY_1,
        url="https://news.example.it/fallimenti-moda",
        title="Fallimento nel settore abbigliamento e moda",
    )
    rejected, rejection_reason = adapt_italy_signal_to_entity_memory(generic)
    assert rejected is None
    assert rejection_reason == "NO_EXPLICIT_ITALIAN_ENTITY"


def test_two_days_for_same_company_build_one_stable_case() -> None:
    first = _aurora_signal(
        observed_at=DAY_1,
        url="https://source-one.example.it/aurora-liquidazione",
    )
    second = _aurora_signal(
        observed_at=DAY_2,
        url="https://source-two.example.it/aurora-magazzino",
    )

    report = build_italy_case_memory_adapter(
        [first, second],
        observed_at=DAY_2,
    )

    assert report["adapted_entity_signal_count"] == 2
    assert report["persistent_case_count"] == 1
    case = report["cases"][0]
    assert case["entity_key"] == "aurora moda"
    assert case["entity_source_signal_count"] == 2
    assert case["first_seen"] == DAY_1.isoformat()
    assert case["last_seen"] == DAY_2.isoformat()
    assert len(case["source_urls"]) == 2

    first_only = build_italy_case_memory_adapter([first], observed_at=DAY_1)
    assert first_only["cases"][0]["case_id"] == case["case_id"]


def test_italy_follow_up_rotates_through_five_inventory_hunt_stages() -> None:
    signal = _aurora_signal(
        observed_at=DAY_1,
        url="https://news.example.it/aurora-liquidazione",
    )

    stages: list[str] = []
    queries: list[str] = []
    for offset, day in enumerate((16, 17, 18, 19, 20)):
        report = build_italy_case_memory_adapter(
            [signal],
            observed_at=datetime(2026, 8, day, 10, 0, tzinfo=timezone.utc),
        )
        stages.append(report["follow_up_plan"][0]["follow_up_stage"])
        queries.append(report["follow_up_plan"][0]["query"])

    assert stages == [
        "MAGAZZINO",
        "ASTA",
        "SVENDITA",
        "LIQUIDAZIONE",
        "LOTTI_CONCRETI",
    ]
    assert "magazzino" in queries[0]
    assert "asta" in queries[1]
    assert "svendita" in queries[2]
    assert "liquidazione giudiziale" in queries[3]
    assert "lotto" in queries[4]


class _FakeProvider:
    def __init__(self, hits: list[SearchHit]) -> None:
        self.hits = hits
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, *, count: int = 10) -> list[SearchHit]:
        self.calls.append((query, count))
        return self.hits[:count]


def test_news_today_inventory_tomorrow_stays_on_same_case_and_surfaces_lead(
    tmp_path: Path,
) -> None:
    first = _aurora_signal(
        observed_at=DAY_1,
        url="https://news.example.it/aurora-liquidazione",
    )

    day_one = run_italy_case_memory_cycle(
        [first],
        input_root=tmp_path,
        environment={},
        observed_at=DAY_1,
        max_cases=1,
    )
    assert day_one["persistent_case_count"] == 1
    case_id = day_one["cases"][0]["case_id"]
    assert day_one["follow_up"]["status"] == "SKIPPED_NO_API_KEY"

    second = _aurora_signal(
        observed_at=DAY_2,
        url="https://news-two.example.it/aurora-procedura",
    )
    provider = _FakeProvider(
        [
            SearchHit(
                title="Aurora Moda S.r.l. - asta di lotto abbigliamento",
                url="https://aste.example.it/aurora-lotto-800-capi",
                description=(
                    "Lotto di 800 capi in vendita. Stock disponibile con prezzo "
                    "e dettagli della vendita giudiziaria."
                ),
                provider="Fake Brave",
            )
        ]
    )

    day_two = run_italy_case_memory_cycle(
        [second],
        input_root=tmp_path,
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, key: provider,
        observed_at=DAY_2,
        max_cases=1,
        results_per_case=5,
    )

    assert day_two["persistent_case_count"] == 1
    case = day_two["cases"][0]
    assert case["case_id"] == case_id
    assert case["first_seen"] == DAY_1.isoformat()
    assert case["last_seen"] == DAY_2.isoformat()
    assert case["entity_source_signal_count"] == 2
    assert day_two["persistence"]["loaded_italy_entity_signal_count"] == 2

    assert provider.calls
    assert "asta" in provider.calls[0][0].casefold()
    follow_up = day_two["follow_up"]
    assert follow_up["status"] == "SUCCESS"
    assert follow_up["commercial_lead_count"] == 1
    row = follow_up["cases"][0]
    assert row["case_id"] == case_id
    assert row["follow_up_stage"] == "ASTA"
    assert row["follow_up_state"] == "COMMERCIAL_LEAD_REQUIRES_SOURCE_VERIFICATION"
    lead = row["leads"][0]
    assert lead["source_url"] == "https://aste.example.it/aurora-lotto-800-capi"
    assert lead["verification_status"] == "UNVERIFIED_PUBLIC_WEB_SEARCH_HIT"
    assert lead["commercial_facts_confirmed"] is False
    assert lead["source_page_verification_required"] is True
    assert lead["promotion_to_opportunity_allowed"] is False
