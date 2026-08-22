from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.adaptive_keyword_learning import KeywordEvaluationResult
from opportunity_engine.daily_learning_operator import (
    DailyLearningPolicy,
    merge_case_memory,
    run_daily_learning_cycle,
)
from opportunity_engine.learned_query_overlay import (
    build_learned_query_overlay,
    learned_terms_for_market,
    merge_learned_query_overlays,
)
from opportunity_engine.missed_opportunity_learning import (
    DiscoveryTrace,
    MissedOpportunityCase,
)


def case(case_id: str, text: str, *, root_cause: str | None = "QUERY_GAP"):
    return MissedOpportunityCase(
        case_id=case_id,
        market_code="NO",
        discovered_by="human",
        observed_at=datetime(2026, 8, 22, tzinfo=timezone.utc),
        opportunity_type="STOCK_LIQUIDATION",
        stock_proven=True,
        ground_truth_company=f"Company {case_id} AS",
        ground_truth_url=f"https://example.no/{case_id}",
        trace=DiscoveryTrace(query_generated=False),
        learning_evidence_text=text,
        root_cause=root_cause,
        learning_status="DIAGNOSED" if root_cause else "PENDING",
    )


def evaluation(term: str, precision: float = 0.5):
    return KeywordEvaluationResult(
        term=term,
        market_code="NO",
        status="PROVEN",
        recovered_case_ids=("MISS-OLD",),
        raw_hit_count=2,
        verified_relevant_count=1,
        precision=precision,
        min_recovered_cases=1,
        min_precision=0.2,
        automatic_activation=False,
    )


def test_merge_case_memory_is_idempotent_and_preserves_existing_learning() -> None:
    existing = case("MISS-1", "Avviklingssalg med restlager.")
    existing = MissedOpportunityCase(
        **{**existing.__dict__, "learned_patterns": ("avviklingssalg",), "learning_status": "RECOVERED"}
    ) if hasattr(existing, "__dict__") else existing

    # frozen/slots dataclass has no __dict__; create the learned instance directly.
    existing = MissedOpportunityCase(
        case_id="MISS-1",
        market_code="NO",
        discovered_by="human",
        observed_at=datetime(2026, 8, 22, tzinfo=timezone.utc),
        opportunity_type="STOCK_LIQUIDATION",
        stock_proven=True,
        ground_truth_company="Company MISS-1 AS",
        ground_truth_url="https://example.no/MISS-1",
        trace=DiscoveryTrace(query_generated=False),
        learning_evidence_text="Avviklingssalg med restlager.",
        learned_patterns=("avviklingssalg",),
        root_cause="QUERY_GAP",
        learning_status="RECOVERED",
    )
    duplicate_inbox = case("MISS-1", "Different text that must not reset state")
    new_case = case("MISS-2", "Sluttlager med arbeidsklær.")

    merged = merge_case_memory([existing], [duplicate_inbox, new_case])

    assert [item.case_id for item in merged] == ["MISS-1", "MISS-2"]
    assert merged[0].learning_status == "RECOVERED"
    assert merged[0].learned_patterns == ("avviklingssalg",)


def test_no_query_gap_cases_means_zero_learning_search_requests() -> None:
    calls: list[tuple[str, str]] = []
    parser_case = case("MISS-P", "Avviklingssalg med restlager.", root_cause="PARSER_GAP")

    outcome = run_daily_learning_cycle(
        existing_cases=[parser_case],
        inbox_cases=[],
        active_queries=[],
        search=lambda term, market: calls.append((term, market)) or [],
    )

    assert calls == []
    assert outcome.report["candidate_count"] == 0
    assert outcome.report["learning_search_requests"] == 0


def test_learning_cycle_never_evaluates_more_than_policy_budget() -> None:
    cases = [
        case("MISS-1", "Avviklingssalg med restlager."),
        case("MISS-2", "Sluttlager med arbeidsklær."),
        case("MISS-3", "Tømmesalg og varelager."),
    ]
    calls: list[tuple[str, str]] = []

    def search(term: str, market: str):
        calls.append((term, market))
        return []

    outcome = run_daily_learning_cycle(
        existing_cases=cases,
        inbox_cases=[],
        active_queries=[],
        search=search,
        policy=DailyLearningPolicy(max_candidates_per_run=2),
    )

    assert len(calls) == 2
    assert outcome.report["learning_search_requests"] == 2
    assert outcome.report["candidate_count"] >= 3
    assert outcome.report["evaluated_candidate_count"] == 2


def test_proven_keyword_is_added_without_dropping_previous_overlay() -> None:
    old_overlay = build_learned_query_overlay([evaluation("restlager", 0.8)])
    learning_case = case("MISS-NEW", "Sluttlager med arbeidsklær.")

    def search(term: str, market: str):
        if term == "sluttlager":
            return [
                {
                    "url": "https://example.no/MISS-NEW",
                    "verified_relevant": True,
                },
                {"url": "https://noise.example/1"},
            ]
        return []

    outcome = run_daily_learning_cycle(
        existing_cases=[learning_case],
        inbox_cases=[],
        active_queries=[],
        search=search,
        existing_overlay=old_overlay,
        policy=DailyLearningPolicy(max_candidates_per_run=5),
    )

    terms = learned_terms_for_market(outcome.overlay, "NO")
    assert "restlager" in terms
    assert "sluttlager" in terms
    learned_case = next(item for item in outcome.cases if item.case_id == "MISS-NEW")
    assert "sluttlager" in learned_case.learned_patterns
    assert learned_case.learning_status == "RECOVERED"


def test_overlay_merge_keeps_highest_precision_and_bounds_terms() -> None:
    old = build_learned_query_overlay(
        [evaluation("restlager", 0.4), evaluation("lagersalg", 0.9)]
    )
    new = build_learned_query_overlay(
        [evaluation("restlager", 0.8), evaluation("sluttlager", 0.7)]
    )

    merged = merge_learned_query_overlays(old, new, max_terms_per_market=2)

    rows = merged["markets"]["NO"]
    assert [row["term"] for row in rows] == ["lagersalg", "restlager"]
    restlager = next(row for row in rows if row["term"] == "restlager")
    assert restlager["precision"] == 0.8


def test_search_disabled_preserves_candidates_without_spending_requests() -> None:
    learning_case = case("MISS-1", "Sluttlager med arbeidsklær.")
    calls: list[tuple[str, str]] = []

    outcome = run_daily_learning_cycle(
        existing_cases=[learning_case],
        inbox_cases=[],
        active_queries=[],
        search=lambda term, market: calls.append((term, market)) or [],
        search_enabled=False,
        search_skip_reason="SKIPPED_COST_GUARD",
    )

    assert calls == []
    assert outcome.report["candidate_count"] >= 1
    assert outcome.report["evaluated_candidate_count"] == 0
    assert outcome.report["learning_search_requests"] == 0
    assert outcome.report["search_status"] == "SKIPPED_COST_GUARD"
