from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.missed_opportunity_learning import (
    DiscoveryTrace,
    MissedOpportunityCase,
    build_learning_metrics,
    diagnose_root_cause,
    load_missed_opportunity_memory,
    run_replay,
    save_missed_opportunity_memory,
)


def _case(*, trace: DiscoveryTrace, learned_patterns: tuple[str, ...] = ()) -> MissedOpportunityCase:
    return MissedOpportunityCase(
        case_id="MISS-NO-0001",
        market_code="NO",
        discovered_by="human",
        observed_at=datetime(2026, 8, 21, 10, 30, tzinfo=timezone.utc),
        opportunity_type="STOCK_LIQUIDATION",
        stock_proven=True,
        ground_truth_company="Eksempel Mote AS",
        ground_truth_url="https://example.no/avviklingssalg",
        trace=trace,
        learned_patterns=learned_patterns,
    )


def test_root_cause_is_the_first_failed_pipeline_stage() -> None:
    trace = DiscoveryTrace(
        query_generated=True,
        search_hit=True,
        retrieved=True,
        parsed=True,
        entity_linked=True,
        classified_relevant=False,
        verified=None,
        ranked=None,
        reported=None,
        timely_discovery=True,
    )

    assert diagnose_root_cause(trace) == "CLASSIFICATION_GAP"


def test_root_cause_distinguishes_query_source_and_timing_gaps() -> None:
    assert diagnose_root_cause(DiscoveryTrace(query_generated=False)) == "QUERY_GAP"
    assert diagnose_root_cause(
        DiscoveryTrace(query_generated=True, search_hit=False)
    ) == "SOURCE_GAP"
    assert diagnose_root_cause(
        DiscoveryTrace(
            query_generated=True,
            search_hit=True,
            retrieved=True,
            timely_discovery=False,
        )
    ) == "TIMING_GAP"


def test_replay_hides_ground_truth_and_can_prove_pattern_recovery() -> None:
    case = _case(
        trace=DiscoveryTrace(query_generated=True, search_hit=False),
        learned_patterns=("avviklingssalg",),
    )
    seen_context: dict = {}

    def discover(context: dict) -> list[dict]:
        seen_context.update(context)
        # The discovery side gets the learned pattern, but not the answer.
        assert "ground_truth_company" not in context
        assert "ground_truth_url" not in context
        assert "company" not in context
        assert "url" not in context
        if "avviklingssalg" in context["learned_patterns"]:
            return [
                {
                    "company": "Eksempel Mote AS",
                    "url": "https://example.no/avviklingssalg",
                }
            ]
        return []

    result = run_replay(case, discover)

    assert seen_context["market_code"] == "NO"
    assert result.recovered is True
    assert result.matched_by in {"company", "url", "company+url"}
    assert result.ground_truth_exposed is False


def test_replay_rejects_unrelated_candidate() -> None:
    case = _case(
        trace=DiscoveryTrace(query_generated=True, search_hit=False),
        learned_patterns=("avviklingssalg",),
    )

    result = run_replay(
        case,
        lambda context: [
            {"company": "Annen Bedrift AS", "url": "https://other.example/sale"}
        ],
    )

    assert result.recovered is False
    assert result.matched_by is None


def test_memory_round_trip_preserves_diagnosis_and_learning_state(tmp_path: Path) -> None:
    case = _case(
        trace=DiscoveryTrace(
            query_generated=True,
            search_hit=True,
            retrieved=True,
            parsed=False,
        ),
        learned_patterns=("restlager", "avviklingssalg"),
    ).with_diagnosis()
    path = tmp_path / "missed_opportunities.json"

    save_missed_opportunity_memory(path, [case])
    loaded = load_missed_opportunity_memory(path)

    assert len(loaded) == 1
    restored = loaded[0]
    assert restored.case_id == case.case_id
    assert restored.root_cause == "PARSER_GAP"
    assert restored.learned_patterns == ("restlager", "avviklingssalg")
    assert restored.ground_truth_company == "Eksempel Mote AS"


def test_learning_metrics_measure_recovery_and_repeat_misses() -> None:
    recovered = _case(
        trace=DiscoveryTrace(query_generated=False),
        learned_patterns=("avviklingssalg",),
    ).with_diagnosis()
    unresolved = MissedOpportunityCase(
        case_id="MISS-NO-0002",
        market_code="NO",
        discovered_by="human",
        observed_at=datetime(2026, 8, 22, 8, 0, tzinfo=timezone.utc),
        opportunity_type="STOCK_LIQUIDATION",
        stock_proven=True,
        ground_truth_company="Ny Butikk AS",
        ground_truth_url="https://example.no/restlager",
        trace=DiscoveryTrace(query_generated=True, search_hit=False),
        learned_patterns=("restlager",),
        repeat_miss=True,
    ).with_diagnosis()

    replay_results = [
        run_replay(
            recovered,
            lambda context: [
                {
                    "company": "Eksempel Mote AS",
                    "url": "https://example.no/avviklingssalg",
                }
            ],
        ),
        run_replay(unresolved, lambda context: []),
    ]

    metrics = build_learning_metrics([recovered, unresolved], replay_results)

    assert metrics["known_missed_opportunities"] == 2
    assert metrics["diagnosed_count"] == 2
    assert metrics["recovered_count"] == 1
    assert metrics["unresolved_count"] == 1
    assert metrics["recovery_rate"] == 0.5
    assert metrics["repeat_miss_count"] == 1
    assert metrics["repeat_miss_rate"] == 0.5
    assert metrics["root_cause_counts"] == {"QUERY_GAP": 1, "SOURCE_GAP": 1}
