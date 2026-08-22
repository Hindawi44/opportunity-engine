from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.daily_learning_operator import DailyLearningPolicy, run_daily_learning_cycle
from opportunity_engine.missed_opportunity_learning import DiscoveryTrace, MissedOpportunityCase

TERM = "avviklingssalg"
SOURCE_ID = "auto-query-gap:no:bauhaus-transfer-test"
HOLDOUT_A = "HOLDOUT-NO-MARNBURG-2008"
HOLDOUT_B = "HOLDOUT-NO-FAGHANDEL-SURNADAL-2024"


def _source_case() -> MissedOpportunityCase:
    return MissedOpportunityCase(
        case_id=SOURCE_ID,
        market_code="NO",
        discovered_by="AUTOMATIC_INDEPENDENT_QUERY_GAP_SCOUT",
        observed_at=datetime(2026, 8, 22, 18, 0, tzinfo=timezone.utc),
        opportunity_type="VERIFIED_STORE_CLOSURE_INVENTORY_LIQUIDATION",
        stock_proven=True,
        ground_truth_company="BAUHAUS",
        ground_truth_url="https://www.bauhaus.no/bauhaus-norge-informasjon",
        trace=DiscoveryTrace(query_generated=False),
        learning_evidence_text="BAUHAUS avvikler virksomheten og lagerbeholdningen selges ut.",
        diagnosed_query_gap_terms=(TERM,),
    ).with_diagnosis()


def _holdout(case_id: str, company: str, url: str) -> MissedOpportunityCase:
    return MissedOpportunityCase(
        case_id=case_id,
        market_code="NO",
        discovered_by="HIDDEN_VALIDATION_PUBLIC_SOURCE",
        observed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        opportunity_type="STORE_CLOSURE_STOCK_LIQUIDATION",
        stock_proven=True,
        ground_truth_company=company,
        ground_truth_url=url,
        trace=DiscoveryTrace(),
        root_cause="VALIDATION_HOLDOUT",
        learning_status="HOLDOUT",
    )


def test_pending_shadow_transfer_is_reproposed_until_second_independent_holdout() -> None:
    source = _source_case()
    holdout_a = _holdout(HOLDOUT_A, "Marnburg Interiør AS", "https://www.dagsavisen.no/nyheter/marnburg-legger-ned-ostehuset-flytter-inn/6791594")
    holdout_b = _holdout(HOLDOUT_B, "Coop Faghandel Surnadal", "https://www.trollheimsporten.no/coop-surnadal-sport1-surnadal-surnadalsnytt/avviklingssalg-pa-faghandel-surnadal/288445")
    policy = DailyLearningPolicy(max_candidates_per_run=1, min_precision=0.2)

    first = run_daily_learning_cycle(
        existing_cases=[source], inbox_cases=[], validation_cases=[holdout_a], active_queries=[],
        search=lambda term, market: [{"url": holdout_a.ground_truth_url}] if term == TERM else [],
        policy=policy,
    )
    first_row = first.shadow_overlay["markets"]["NO"][0]
    assert first_row["transfer_validation_case_ids"] == [HOLDOUT_A]
    assert first_row["independent_transfer_case_count"] == 1

    second = run_daily_learning_cycle(
        existing_cases=first.cases, inbox_cases=[], validation_cases=[holdout_a, holdout_b], active_queries=[],
        search=lambda term, market: [{"url": holdout_b.ground_truth_url}] if term == TERM else [],
        existing_shadow_overlay=first.shadow_overlay, existing_overlay=first.overlay, policy=policy,
    )
    assert second.report["learning_search_requests"] == 1
    assert second.candidates[0].term == TERM
    second_row = second.shadow_overlay["markets"]["NO"][0]
    assert second_row["transfer_validation_case_ids"] == sorted([HOLDOUT_A, HOLDOUT_B])
    assert second_row["independent_transfer_case_count"] == 2


def test_replicated_shadow_term_stops_consuming_learning_budget() -> None:
    source = _source_case()
    holdout_a = _holdout(HOLDOUT_A, "Marnburg Interiør AS", "https://example.no/a")
    holdout_b = _holdout(HOLDOUT_B, "Coop Faghandel Surnadal", "https://example.no/b")
    policy = DailyLearningPolicy(max_candidates_per_run=1, min_precision=0.2)

    first = run_daily_learning_cycle(
        existing_cases=[source], inbox_cases=[], validation_cases=[holdout_a, holdout_b], active_queries=[],
        search=lambda term, market: [{"url": holdout_a.ground_truth_url}, {"url": holdout_b.ground_truth_url}] if term == TERM else [],
        policy=policy,
    )
    assert first.shadow_overlay["markets"]["NO"][0]["independent_transfer_case_count"] == 2

    def should_not_search(term: str, market: str):
        raise AssertionError("replicated shadow term should not be re-evaluated")

    second = run_daily_learning_cycle(
        existing_cases=first.cases, inbox_cases=[], validation_cases=[holdout_a, holdout_b], active_queries=[],
        search=should_not_search, existing_shadow_overlay=first.shadow_overlay,
        existing_overlay=first.overlay, policy=policy,
    )
    assert second.report["learning_search_requests"] == 0
    assert second.report["candidate_count"] == 0
