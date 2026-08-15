from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.signal_follow_up_continuity import (
    build_persistent_entity_cases,
    build_persistent_entity_follow_up_plan,
    run_signal_follow_up_engine_with_continuity,
)


FIRST_SEEN = "2026-08-15T14:18:02+00:00"


def _entity_signal(
    signal_id: str,
    label: str,
    entity_key: str,
    market: str,
    score: int,
    source_url: str,
) -> dict:
    return {
        "signal_id": signal_id,
        "signal_type": "INSOLVENCY_OR_LIQUIDATION",
        "source": "Cross-source scent expansion V2 + entity quality gate V1",
        "source_country": market,
        "source_url": source_url,
        "title": f"{label} insolvency signal",
        "first_observed_at": FIRST_SEEN,
        "latest_observed_at": FIRST_SEEN,
        "observed_at": FIRST_SEEN,
        "status": "WATCH",
        "confidence": 0.72,
        "metadata": {
            "entity_scent_classification": "ENTITY_SCENT",
            "entity_scent_quality_gate": "ENTITY_SCENT_QUALITY_GATE_V1",
            "entity_key": entity_key,
            "entity_label": label,
            "entity_cluster_score": score,
            "entity_evidence_count": 1,
            "entity_independent_source_count": 1,
            "signal_only": True,
            "source_page_verification_required": True,
            "promotion_to_opportunity_allowed": False,
            "query_id": "volatile-test-query",
            "source_rank": 1,
        },
        "evidence": [],
        "missing_information": [],
    }


def _three_run_151_entities() -> list[dict]:
    return [
        _entity_signal(
            "adenauer-1",
            "Adenauer & Co",
            "adenauer & co",
            "DE",
            90,
            "https://example.test/adenauer",
        ),
        _entity_signal(
            "stores-1",
            "Stores For You AB",
            "stores for you",
            "SE",
            85,
            "https://example.test/stores-for-you",
        ),
        _entity_signal(
            "schuemer-1",
            "Schümer Textil GmbH",
            "schümer textil",
            "DE",
            75,
            "https://example.test/schuemer",
        ),
    ]


def _recent_current_case(index: int) -> dict:
    return {
        "case_id": f"recent-no-{index}",
        "case_type": "COMPANY_LIQUIDATION",
        "case_title": f"Recent Norway company {index}",
        "case_status": "WATCH",
        "countries": ["NO"],
        "grouping_basis": "ITEM",
        "grouping_key": f"item:recent-{index}",
        "commercial_strength": 99.0,
        "last_seen": "2026-08-15T15:30:00+00:00",
        "source_urls": [],
    }


def test_run_151_entity_cases_are_prioritized_before_newer_generic_cases() -> None:
    cases_report = {"cases": [_recent_current_case(i) for i in range(6)]}

    report = run_signal_follow_up_engine_with_continuity(
        cases_report,
        entity_signals=_three_run_151_entities(),
        environment={},
        observed_at=datetime(2026, 8, 15, 16, 0, tzinfo=timezone.utc),
        max_cases=4,
    )

    assert report["status"] == "SKIPPED_NO_API_KEY"
    assert report["persistent_entity_case_count"] == 3
    assert report["persistent_entity_selected_count"] == 3
    assert report["selected_case_count"] == 4
    assert [row["target_label"] for row in report["cases"][:3]] == [
        "Adenauer & Co",
        "Stores For You AB",
        "Schümer Textil GmbH",
    ]
    assert [row["follow_up_stage"] for row in report["cases"][:3]] == [
        "WARENBESTAND",
        "VARULAGER",
        "WARENBESTAND",
    ]
    assert report["promotion_to_opportunity_allowed"] is False
    assert report["automatic_contact"] is False
    assert report["automatic_bid"] is False
    assert report["automatic_purchase"] is False
    assert report["automatic_payment"] is False


def test_adenauer_follow_up_rotates_across_five_calendar_day_intents() -> None:
    cases = build_persistent_entity_cases(
        [_three_run_151_entities()[0]],
        observed_at=datetime(2026, 8, 15, 16, 0, tzinfo=timezone.utc),
    )

    observed_dates = [15, 16, 17, 18, 19]
    stages: list[str] = []
    queries: list[str] = []
    for day in observed_dates:
        plan = build_persistent_entity_follow_up_plan(
            cases,
            observed_at=datetime(2026, 8, day, 16, 0, tzinfo=timezone.utc),
            max_cases=1,
        )
        stages.append(plan[0]["follow_up_stage"])
        queries.append(plan[0]["query"])

    assert stages == [
        "WARENBESTAND",
        "AUKTION",
        "LAGERVERKAUF",
        "VERWERTUNG",
        "KONKRETE_LOTS",
    ]
    assert "Warenbestand" in queries[0]
    assert "Auktion" in queries[1]
    assert "Lagerverkauf" in queries[2]
    assert "Verwertung" in queries[3]
    assert "Warenposten" in queries[4]


class _FakeProvider:
    def __init__(self, hits: list[SearchHit]) -> None:
        self.hits = hits
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, *, count: int = 10) -> list[SearchHit]:
        self.calls.append((query, count))
        return self.hits[:count]


def test_verwertung_day_can_surface_only_an_unverified_commercial_lead() -> None:
    provider = _FakeProvider(
        [
            SearchHit(
                title="Adenauer & Co Verwertung des Warenbestands",
                url="https://auction.example/adenauer-verwertung",
                description="Warenbestand aus der Verwertung wird zum Verkauf angeboten.",
                provider="Brave Search",
            )
        ]
    )

    report = run_signal_follow_up_engine_with_continuity(
        {"cases": []},
        entity_signals=[_three_run_151_entities()[0]],
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, key: provider,
        observed_at=datetime(2026, 8, 18, 16, 0, tzinfo=timezone.utc),
        max_cases=1,
        results_per_case=5,
    )

    assert provider.calls
    assert "Verwertung" in provider.calls[0][0]
    assert report["status"] == "SUCCESS"
    assert report["commercial_lead_count"] == 1
    lead = report["cases"][0]["leads"][0]
    assert lead["source_url"] == "https://auction.example/adenauer-verwertung"
    assert lead["verification_status"] == "UNVERIFIED_PUBLIC_WEB_SEARCH_HIT"
    assert lead["commercial_facts_confirmed"] is False
    assert lead["source_page_verification_required"] is True
    assert lead["promotion_to_opportunity_allowed"] is False


def test_same_entity_signals_cluster_into_one_persistent_case() -> None:
    first = _three_run_151_entities()[0]
    second = dict(first)
    second["signal_id"] = "adenauer-2"
    second["source_url"] = "https://example.test/adenauer-second-source"
    second["title"] = "Second independent Adenauer & Co source"

    cases = build_persistent_entity_cases(
        [first, second],
        observed_at=datetime(2026, 8, 15, 16, 0, tzinfo=timezone.utc),
    )

    assert len(cases) == 1
    assert cases[0]["entity_key"] == "adenauer and co"
    assert cases[0]["entity_source_signal_count"] == 2
    assert len(cases[0]["source_urls"]) == 2
