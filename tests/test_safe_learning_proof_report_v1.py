from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.adaptive_keyword_learning import KeywordEvaluationResult
from opportunity_engine.learned_query_overlay import build_learned_query_overlay
from opportunity_engine.missed_opportunity_learning import (
    DiscoveryTrace,
    MissedOpportunityCase,
)
from opportunity_engine.safe_learning_proof import build_query_gap_safe_learning_proof


def _case(case_id: str = "real-query-gap-1") -> MissedOpportunityCase:
    return MissedOpportunityCase(
        case_id=case_id,
        market_code="NO",
        discovered_by="AUTOMATIC_SOURCE_VERIFIED_GAP_DETECTOR",
        observed_at=datetime(2026, 8, 22, 8, 0, tzinfo=timezone.utc),
        opportunity_type="VERIFIED_BULK_CLOTHING_STOCK",
        stock_proven=True,
        ground_truth_company="Eksempel Arbeidsklær AS",
        ground_truth_url="https://example.no/verified-stock-lot",
        trace=DiscoveryTrace(query_generated=False),
        root_cause="QUERY_GAP",
        learning_status="DIAGNOSED",
    )


def _evaluation(
    *,
    term: str = "sluttlager",
    case_id: str = "real-query-gap-1",
    precision: float = 0.5,
    raw_hit_count: int = 4,
    relevant_count: int = 2,
) -> KeywordEvaluationResult:
    return KeywordEvaluationResult(
        term=term,
        market_code="NO",
        status="PROVEN",
        recovered_case_ids=(case_id,),
        raw_hit_count=raw_hit_count,
        verified_relevant_count=relevant_count,
        precision=precision,
        min_recovered_cases=1,
        min_precision=0.2,
        automatic_activation=False,
    )


def test_real_query_gap_with_no_shadow_recovery_reports_no_proof_yet() -> None:
    proof = build_query_gap_safe_learning_proof(
        [_case()],
        shadow_overlay=build_learned_query_overlay([]),
        active_overlay=build_learned_query_overlay([]),
        min_precision=0.2,
    )

    assert proof["status"] == "NO_SHADOW_RECOVERY_YET"
    assert proof["query_gap_case_count"] == 1
    assert proof["shadow_recovered_case_count"] == 0
    assert proof["promotion_eligible_count"] == 0
    assert proof["automatic_promotion"] is False


def test_shadow_recovery_produces_one_clear_promotion_eligible_proof() -> None:
    case = _case()
    shadow = build_learned_query_overlay([_evaluation()])

    proof = build_query_gap_safe_learning_proof(
        [case],
        shadow_overlay=shadow,
        active_overlay=build_learned_query_overlay([]),
        min_precision=0.2,
    )

    assert proof["status"] == "SHADOW_PASSED"
    assert proof["shadow_recovered_case_count"] == 1
    assert proof["promotion_eligible_count"] == 1
    [row] = proof["cases"]
    assert row["case_id"] == case.case_id
    assert row["baseline_missed"] is True
    assert row["baseline_root_cause"] == "QUERY_GAP"
    assert row["shadow_recovered"] is True
    assert row["shadow_term"] == "sluttlager"
    assert row["shadow_precision"] == 0.5
    assert row["shadow_raw_hit_count"] == 4
    assert row["shadow_verified_relevant_count"] == 2
    assert row["shadow_false_positive_count"] == 2
    assert row["shadow_false_positive_rate"] == 0.5
    assert row["production_term_active"] is False
    assert row["production_unchanged_during_shadow"] is True
    assert row["promotion_eligible"] is True
    assert row["automatic_promotion"] is False


def test_noisy_shadow_recovery_is_not_promotion_eligible() -> None:
    shadow = build_learned_query_overlay(
        [_evaluation(precision=0.1, raw_hit_count=10, relevant_count=1)]
    )

    proof = build_query_gap_safe_learning_proof(
        [_case()],
        shadow_overlay=shadow,
        active_overlay=build_learned_query_overlay([]),
        min_precision=0.2,
    )

    assert proof["status"] == "SHADOW_RECOVERED_BUT_NOISY"
    assert proof["promotion_eligible_count"] == 0
    assert proof["cases"][0]["promotion_eligible"] is False


def test_explicitly_promoted_term_is_reported_as_promoted_not_shadow_eligible() -> None:
    shadow = build_learned_query_overlay([_evaluation()])
    active = {
        **shadow,
        "markets": {
            "NO": [
                {
                    **shadow["markets"]["NO"][0],
                    "promotion_status": "PROMOTED",
                    "activation_source": "EXPLICIT_PROMOTION",
                }
            ]
        },
        "promotion_gate_enforced": True,
    }

    proof = build_query_gap_safe_learning_proof(
        [_case()],
        shadow_overlay=shadow,
        active_overlay=active,
        min_precision=0.2,
    )

    assert proof["status"] == "PROMOTED_PROOF_EXISTS"
    assert proof["promoted_proof_count"] == 1
    assert proof["promotion_eligible_count"] == 0
    row = proof["cases"][0]
    assert row["production_term_active"] is True
    assert row["production_unchanged_during_shadow"] is False
    assert row["promotion_eligible"] is False


def test_non_query_gap_cases_do_not_claim_query_learning_proof() -> None:
    parser_case = MissedOpportunityCase(
        **{
            "case_id": "parser-1",
            "market_code": "NO",
            "discovered_by": "test",
            "observed_at": datetime(2026, 8, 22, 8, 0, tzinfo=timezone.utc),
            "opportunity_type": "VERIFIED_BULK_CLOTHING_STOCK",
            "stock_proven": True,
            "ground_truth_company": "Example AS",
            "ground_truth_url": "https://example.no/parser",
            "trace": DiscoveryTrace(query_generated=True, search_hit=True, retrieved=True, parsed=False),
            "root_cause": "PARSER_GAP",
            "learning_status": "DIAGNOSED",
        }
    )

    proof = build_query_gap_safe_learning_proof(
        [parser_case],
        shadow_overlay=build_learned_query_overlay([_evaluation(case_id="parser-1")]),
        active_overlay=build_learned_query_overlay([]),
    )

    assert proof["status"] == "NO_QUERY_GAP_CASES"
    assert proof["cases"] == []
