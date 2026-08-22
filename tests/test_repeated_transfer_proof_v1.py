from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.adaptive_keyword_learning import KeywordEvaluationResult
from opportunity_engine.learned_query_overlay import (
    build_learned_query_overlay,
    merge_learned_query_overlays,
)
from opportunity_engine.missed_opportunity_learning import DiscoveryTrace, MissedOpportunityCase
from opportunity_engine.safe_learning_proof import build_query_gap_safe_learning_proof


TERM = "stort avslutningssalg"
MISS_ID = "REAL-MISS-NO-LENE-INTERIOR-2025-08"
HOLDOUT_A = "HOLDOUT-NO-NOREM-BAADE-2010"
HOLDOUT_B = "HOLDOUT-NO-INDEPENDENT-CLOSURE-2"


def _miss() -> MissedOpportunityCase:
    return MissedOpportunityCase(
        case_id=MISS_ID,
        market_code="NO",
        discovered_by="HUMAN_VERIFIED_PUBLIC_SOURCE",
        observed_at=datetime(2025, 8, 28, tzinfo=timezone.utc),
        opportunity_type="STORE_CLOSURE_STOCK_LIQUIDATION",
        stock_proven=True,
        ground_truth_company="Lene Interiør",
        ground_truth_url="https://example.no/lene",
        trace=DiscoveryTrace(query_generated=False),
        learning_evidence_text="Stort avslutningssalg på alle varer i butikken.",
        root_cause="QUERY_GAP",
        learning_status="TRANSFER_PROVEN",
        learned_patterns=(TERM,),
    )


def _evaluation(holdout_id: str, *, precision: float = 0.5) -> KeywordEvaluationResult:
    return KeywordEvaluationResult(
        term=TERM,
        market_code="NO",
        status="PROVEN",
        recovered_case_ids=(holdout_id,),
        raw_hit_count=2,
        verified_relevant_count=1,
        precision=precision,
        min_recovered_cases=1,
        min_precision=0.2,
        automatic_activation=False,
        support_case_ids=(MISS_ID,),
        evaluation_scope="HOLDOUT_TRANSFER",
    )


def test_shadow_overlay_accumulates_unique_holdout_ids_across_runs() -> None:
    first = build_learned_query_overlay([_evaluation(HOLDOUT_A)])
    second = build_learned_query_overlay([_evaluation(HOLDOUT_B)])

    merged = merge_learned_query_overlays(first, second)
    row = merged["markets"]["NO"][0]

    assert row["term"] == TERM
    assert row["recovered_case_ids"] == sorted([HOLDOUT_A, HOLDOUT_B])
    assert row["support_case_ids"] == [MISS_ID]
    assert row["independent_transfer_case_count"] == 2


def test_duplicate_holdout_does_not_count_as_independent_replication() -> None:
    first = build_learned_query_overlay([_evaluation(HOLDOUT_A)])
    repeated = build_learned_query_overlay([_evaluation(HOLDOUT_A, precision=0.8)])

    merged = merge_learned_query_overlays(first, repeated)
    row = merged["markets"]["NO"][0]

    assert row["recovered_case_ids"] == [HOLDOUT_A]
    assert row["independent_transfer_case_count"] == 1
    assert row["precision"] == 0.8


def test_one_hidden_holdout_stays_shadow_pending_replication() -> None:
    shadow = build_learned_query_overlay([_evaluation(HOLDOUT_A)])

    proof = build_query_gap_safe_learning_proof(
        [_miss()],
        shadow_overlay=shadow,
        active_overlay=build_learned_query_overlay([]),
    )

    row = proof["cases"][0]
    assert row["shadow_transfer_proven"] is True
    assert row["independent_transfer_case_count"] == 1
    assert row["min_independent_transfer_cases"] == 2
    assert row["repeated_transfer_proven"] is False
    assert row["promotion_eligible"] is False
    assert proof["promotion_eligible_count"] == 0
    assert proof["status"] == "SHADOW_TRANSFER_PENDING_REPLICATION"


def test_two_hidden_holdouts_make_term_promotion_eligible_without_activating_it() -> None:
    first = build_learned_query_overlay([_evaluation(HOLDOUT_A)])
    second = build_learned_query_overlay([_evaluation(HOLDOUT_B)])
    shadow = merge_learned_query_overlays(first, second)

    proof = build_query_gap_safe_learning_proof(
        [_miss()],
        shadow_overlay=shadow,
        active_overlay=build_learned_query_overlay([]),
    )

    row = proof["cases"][0]
    assert row["independent_transfer_case_count"] == 2
    assert row["repeated_transfer_proven"] is True
    assert row["promotion_eligible"] is True
    assert row["production_term_active"] is False
    assert proof["promotion_eligible_count"] == 1
    assert proof["status"] == "SHADOW_PASSED"
    assert proof["automatic_promotion"] is False
