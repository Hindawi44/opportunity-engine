from __future__ import annotations

from pathlib import Path

from opportunity_engine.adaptive_keyword_learning import KeywordEvaluationResult
from opportunity_engine.learned_query_overlay import (
    build_learned_query_overlay,
    learned_terms_for_market,
)
from opportunity_engine.learning_promotion_gate import (
    load_query_promotion_decisions,
    select_promoted_query_overlay,
)


PROMOTION_CONFIG = Path("config/learning/query_promotions.json")
TERM = "avviklingssalg"


def _transfer_shadow(*case_ids: str):
    evaluation = KeywordEvaluationResult(
        term=TERM,
        market_code="NO",
        status="PROVEN",
        recovered_case_ids=tuple(case_ids),
        raw_hit_count=9,
        verified_relevant_count=len(case_ids),
        precision=len(case_ids) / 9,
        min_recovered_cases=1,
        min_precision=0.20,
        automatic_activation=False,
        support_case_ids=("AUTO-MISS-NO-BAUHAUS",),
        evaluation_scope="HOLDOUT_TRANSFER",
    )
    return build_learned_query_overlay([evaluation])


def test_repository_config_explicitly_promotes_only_avviklingssalg_for_no() -> None:
    decisions = load_query_promotion_decisions(PROMOTION_CONFIG)

    assert decisions == {("NO", TERM): "PROMOTED"}


def test_repository_promotion_decision_cannot_bypass_single_holdout_gate() -> None:
    decisions = load_query_promotion_decisions(PROMOTION_CONFIG)
    active = select_promoted_query_overlay(
        _transfer_shadow("HOLDOUT-NO-SENZE-OF-JOY"),
        decisions,
    )

    assert learned_terms_for_market(active, "NO") == {}
    assert active["active_term_count"] == 0


def test_repository_promotion_decision_activates_after_repeated_transfer_proof() -> None:
    decisions = load_query_promotion_decisions(PROMOTION_CONFIG)
    active = select_promoted_query_overlay(
        _transfer_shadow(
            "HOLDOUT-NO-SENZE-OF-JOY",
            "HOLDOUT-NO-TOFF-OG-LITEN-STEINKJER",
            "HOLDOUT-NO-GAULA-NATURSENTER",
        ),
        decisions,
    )

    assert set(learned_terms_for_market(active, "NO")) == {TERM}
    row = active["markets"]["NO"][0]
    assert row["promotion_status"] == "PROMOTED"
    assert row["activation_source"] == "EXPLICIT_PROMOTION"
    assert row["independent_transfer_case_count"] == 3
    assert active["automatic_query_activation"] is False
