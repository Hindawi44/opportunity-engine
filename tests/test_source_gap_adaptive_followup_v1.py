from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.source_gap_adaptive_followup import (
    build_source_gap_follow_up_plan,
    run_source_gap_adaptive_followup_with_continuity,
    write_source_gap_adaptive_followup_with_continuity,
)
from opportunity_engine.missed_opportunity_learning import (
    DiscoveryTrace,
    MissedOpportunityCase,
    save_missed_opportunity_memory,
)


def _source_gap(
    case_id: str = "source-gap-1",
    *,
    market: str = "NO",
    company: str = "Eksempel Arbeidsklær AS",
    url: str = "https://ny.auksjonen.no/auksjon/gammelt-varelager/424242",
    repeat: bool = False,
    learning_status: str = "DIAGNOSED",
) -> MissedOpportunityCase:
    return MissedOpportunityCase(
        case_id=case_id,
        market_code=market,
        discovered_by="AUTOMATIC_SOURCE_VERIFIED_GAP_DETECTOR",
        observed_at=datetime(2026, 8, 22, 8, 0, tzinfo=timezone.utc),
        opportunity_type="VERIFIED_BULK_CLOTHING_STOCK",
        stock_proven=True,
        ground_truth_company=company,
        ground_truth_url=url,
        trace=DiscoveryTrace(query_generated=True, search_hit=False),
        root_cause="SOURCE_GAP",
        learning_status=learning_status,
        repeat_miss=repeat,
    )


def _entity_signal() -> dict:
    return {
        "signal_id": "entity-1",
        "signal_type": "INSOLVENCY_OR_LIQUIDATION",
        "source": "test",
        "source_country": "DE",
        "source_url": "https://example.test/entity",
        "title": "Other GmbH insolvency",
        "first_observed_at": "2026-08-22T07:00:00+00:00",
        "latest_observed_at": "2026-08-22T07:00:00+00:00",
        "observed_at": "2026-08-22T07:00:00+00:00",
        "status": "WATCH",
        "confidence": 0.8,
        "metadata": {
            "entity_scent_classification": "ENTITY_SCENT",
            "entity_key": "other",
            "entity_label": "Other GmbH",
            "entity_cluster_score": 80,
            "entity_evidence_count": 1,
            "entity_independent_source_count": 1,
        },
        "evidence": [],
        "missing_information": [],
    }


class FakeProvider:
    def __init__(self, hits: list[SearchHit] | None = None) -> None:
        self.hits = list(hits or [])
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, *, count: int = 10):
        self.calls.append((query, count))
        return self.hits[:count]


def test_source_gap_plan_targets_same_proven_domain_and_company() -> None:
    plan = build_source_gap_follow_up_plan([_source_gap()], max_cases=2)

    assert len(plan) == 1
    row = plan[0]
    assert row["follow_up_stage"] == "SOURCE_GAP_DOMAIN_FALLBACK"
    assert row["source_gap_feedback"] is True
    assert "site:ny.auksjonen.no" in row["query"]
    assert '"Eksempel Arbeidsklær AS"' in row["query"]
    assert "varelager" in row["query"]
    assert row["_source_case"]["source_urls"] == [
        "https://ny.auksjonen.no/auksjon/gammelt-varelager/424242"
    ]


def test_recovered_non_repeat_source_gap_does_not_consume_followup_budget() -> None:
    recovered = _source_gap(learning_status="RECOVERED")
    repeated = _source_gap(
        "repeat",
        repeat=True,
        learning_status="RECOVERED",
        url="https://ny.auksjonen.no/auksjon/old/999999",
    )

    plan = build_source_gap_follow_up_plan([recovered, repeated], max_cases=5)

    assert [row["case_id"] for row in plan] == ["repeat"]


def test_source_gap_is_prioritized_inside_existing_max_cases_budget() -> None:
    provider = FakeProvider()

    report = run_source_gap_adaptive_followup_with_continuity(
        {"cases": []},
        entity_signals=[_entity_signal()],
        source_gap_cases=[_source_gap()],
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, key: provider,
        observed_at=datetime(2026, 8, 22, 9, 0, tzinfo=timezone.utc),
        max_cases=2,
        results_per_case=5,
    )

    assert report["source_gap_case_count"] == 1
    assert report["source_gap_selected_count"] == 1
    assert report["persistent_entity_selected_count"] == 1
    assert report["selected_case_count"] == 2
    assert report["search_request_count"] == 2
    assert len(provider.calls) == 2
    assert report["cases"][0]["follow_up_stage"] == "SOURCE_GAP_DOMAIN_FALLBACK"
    assert report["follow_up_case_budget"] == 2
    assert report["selected_case_count"] <= report["follow_up_case_budget"]


def test_source_gap_can_surface_new_exact_item_for_existing_verifier() -> None:
    new_url = "https://ny.auksjonen.no/auksjon/nytt-varelager/434343"
    provider = FakeProvider(
        [
            SearchHit(
                title="Eksempel Arbeidsklær AS - nytt varelager på auksjon",
                url=new_url,
                description="Vareparti og varelager med arbeidsklær selges på auksjon.",
                provider="Brave Search",
            )
        ]
    )

    report = run_source_gap_adaptive_followup_with_continuity(
        {"cases": []},
        entity_signals=[],
        source_gap_cases=[_source_gap()],
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, key: provider,
        max_cases=1,
        results_per_case=5,
    )

    assert report["search_request_count"] == 1
    assert "site:ny.auksjonen.no" in provider.calls[0][0]
    lead = report["cases"][0]["leads"][0]
    assert lead["source_url"] == new_url
    assert lead["verification_status"] == "UNVERIFIED_PUBLIC_WEB_SEARCH_HIT"
    assert lead["source_page_verification_required"] is True
    assert lead["promotion_to_opportunity_allowed"] is False


def test_known_ground_truth_url_is_not_returned_as_new_recovery() -> None:
    known = _source_gap().ground_truth_url
    provider = FakeProvider(
        [
            SearchHit(
                title="Eksempel Arbeidsklær AS varelager",
                url=known,
                description="Varelager og vareparti selges.",
                provider="Brave Search",
            )
        ]
    )

    report = run_source_gap_adaptive_followup_with_continuity(
        {"cases": []},
        entity_signals=[],
        source_gap_cases=[_source_gap()],
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, key: provider,
        max_cases=1,
    )

    assert report["commercial_lead_count"] == 0
    assert report["cases"][0]["leads"] == []


def test_no_api_key_keeps_source_gap_followup_zero_cost() -> None:
    provider = FakeProvider()

    report = run_source_gap_adaptive_followup_with_continuity(
        {"cases": []},
        entity_signals=[],
        source_gap_cases=[_source_gap()],
        environment={},
        provider_factory=lambda market, key: provider,
        max_cases=1,
    )

    assert report["status"] == "SKIPPED_NO_API_KEY"
    assert report["search_request_count"] == 0
    assert provider.calls == []


def test_many_source_gaps_cannot_expand_existing_case_budget() -> None:
    gaps = [
        _source_gap(
            f"gap-{index}",
            url=f"https://ny.auksjonen.no/auksjon/old/{1000 + index}",
        )
        for index in range(5)
    ]
    provider = FakeProvider()

    report = run_source_gap_adaptive_followup_with_continuity(
        {"cases": []},
        entity_signals=[],
        source_gap_cases=gaps,
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, key: provider,
        max_cases=2,
    )

    assert report["source_gap_case_count"] == 5
    assert report["source_gap_selected_count"] == 2
    assert report["selected_case_count"] == 2
    assert report["search_request_count"] == 2
    assert len(provider.calls) == 2


def test_writer_loads_source_gap_cases_from_durable_learning_memory(tmp_path: Path) -> None:
    output_dir = tmp_path / "checkpoint"
    input_root = tmp_path / "inputs"
    output_dir.mkdir(parents=True)
    (output_dir / "unified-market-cases.json").write_text('{"cases": []}', encoding="utf-8")
    save_missed_opportunity_memory(
        input_root / "learning" / "missed-opportunities.json",
        [_source_gap()],
    )
    provider = FakeProvider()

    report = write_source_gap_adaptive_followup_with_continuity(
        output_dir,
        environment={
            "INPUT_ROOT": input_root.as_posix(),
            "BRAVE_SEARCH_API_KEY": "test-key",
        },
        provider_factory=lambda market, key: provider,
        max_cases=1,
    )

    assert report["source_gap_case_count"] == 1
    assert report["source_gap_selected_count"] == 1
    assert report["search_request_count"] == 1
    assert provider.calls
    assert report["automatic_contact"] is False
    assert report["automatic_purchase"] is False
