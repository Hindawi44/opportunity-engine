from __future__ import annotations

from datetime import datetime, timezone
import json

from opportunity_engine.daily_learning_operator import (
    DailyLearningPolicy,
    run_daily_learning_cycle,
)
from opportunity_engine.learning_promotion_gate import (
    load_query_promotion_decisions,
    select_promoted_query_overlay,
)
from opportunity_engine.learned_query_overlay import (
    build_learned_query_overlay,
    learned_terms_for_market,
)
from opportunity_engine.adaptive_keyword_learning import KeywordEvaluationResult
from opportunity_engine.missed_opportunity_learning import DiscoveryTrace, MissedOpportunityCase


def _case(case_id: str = "MISS-1") -> MissedOpportunityCase:
    return MissedOpportunityCase(
        case_id=case_id,
        market_code="NO",
        discovered_by="human",
        observed_at=datetime(2026, 8, 22, tzinfo=timezone.utc),
        opportunity_type="STOCK_LIQUIDATION",
        stock_proven=True,
        ground_truth_company="Example AS",
        ground_truth_url=f"https://example.no/{case_id}",
        trace=DiscoveryTrace(query_generated=False),
        learning_evidence_text="Sluttlager med arbeidsklær selges.",
        root_cause="QUERY_GAP",
        learning_status="DIAGNOSED",
    )


def _evaluation(term: str = "sluttlager") -> KeywordEvaluationResult:
    return KeywordEvaluationResult(
        term=term,
        market_code="NO",
        status="PROVEN",
        recovered_case_ids=("MISS-1",),
        raw_hit_count=2,
        verified_relevant_count=1,
        precision=0.5,
        min_recovered_cases=1,
        min_precision=0.2,
        automatic_activation=False,
    )


def _transfer_evaluation(
    recovered_case_ids: tuple[str, ...],
    *,
    term: str = "avviklingssalg",
) -> KeywordEvaluationResult:
    return KeywordEvaluationResult(
        term=term,
        market_code="NO",
        status="PROVEN",
        recovered_case_ids=recovered_case_ids,
        raw_hit_count=9,
        verified_relevant_count=len(recovered_case_ids),
        precision=len(recovered_case_ids) / 9,
        min_recovered_cases=1,
        min_precision=0.2,
        automatic_activation=False,
        support_case_ids=("MISS-BAUHAUS",),
        evaluation_scope="HOLDOUT_TRANSFER",
    )


def _search(term: str, market: str):
    if term == "sluttlager" and market == "NO":
        return [
            {"url": "https://example.no/MISS-1", "verified_relevant": True},
            {"url": "https://noise.example/1"},
        ]
    return []


def test_proven_term_stays_shadow_only_without_explicit_promotion() -> None:
    outcome = run_daily_learning_cycle(
        existing_cases=[_case()],
        inbox_cases=[],
        active_queries=[],
        search=_search,
        policy=DailyLearningPolicy(max_candidates_per_run=5),
        promotion_decisions={},
    )

    assert "sluttlager" in learned_terms_for_market(outcome.shadow_overlay, "NO")
    assert "sluttlager" not in learned_terms_for_market(outcome.overlay, "NO")
    assert outcome.report["promotion_gate_enforced"] is True
    assert outcome.report["automatic_query_activation"] is False
    assert outcome.report["shadow_proven_term_count"] >= 1
    assert outcome.report["active_learned_term_count"] == 0


def test_explicit_promotion_activates_only_a_proven_shadow_term() -> None:
    shadow = build_learned_query_overlay([_evaluation()])
    active = select_promoted_query_overlay(
        shadow,
        {("NO", "sluttlager"): "PROMOTED", ("NO", "not-proven"): "PROMOTED"},
    )

    terms = learned_terms_for_market(active, "NO")
    assert set(terms) == {"sluttlager"}
    row = active["markets"]["NO"][0]
    assert row["promotion_status"] == "PROMOTED"
    assert row["activation_source"] == "EXPLICIT_PROMOTION"
    assert active["automatic_query_activation"] is False
    assert active["promotion_gate_enforced"] is True


def test_explicit_promotion_cannot_activate_single_holdout_transfer_proof() -> None:
    shadow = build_learned_query_overlay(
        [_transfer_evaluation(("HOLDOUT-NO-SENZE-OF-JOY",))]
    )

    active = select_promoted_query_overlay(
        shadow,
        {("NO", "avviklingssalg"): "PROMOTED"},
    )

    assert learned_terms_for_market(active, "NO") == {}
    assert active["active_term_count"] == 0


def test_explicit_promotion_can_activate_repeated_independent_transfer_proof() -> None:
    shadow = build_learned_query_overlay(
        [
            _transfer_evaluation(
                (
                    "HOLDOUT-NO-SENZE-OF-JOY",
                    "HOLDOUT-NO-TOFF-OG-LITEN-STEINKJER",
                )
            )
        ]
    )

    active = select_promoted_query_overlay(
        shadow,
        {("NO", "avviklingssalg"): "PROMOTED"},
    )

    assert set(learned_terms_for_market(active, "NO")) == {"avviklingssalg"}
    row = active["markets"]["NO"][0]
    assert row["independent_transfer_case_count"] == 2
    assert row["promotion_status"] == "PROMOTED"


def test_disabled_decision_rolls_back_active_term_without_deleting_shadow_evidence() -> None:
    shadow = build_learned_query_overlay([_evaluation()])

    promoted = select_promoted_query_overlay(
        shadow,
        {("NO", "sluttlager"): "PROMOTED"},
    )
    disabled = select_promoted_query_overlay(
        shadow,
        {("NO", "sluttlager"): "DISABLED"},
    )

    assert "sluttlager" in learned_terms_for_market(promoted, "NO")
    assert learned_terms_for_market(disabled, "NO") == {}
    assert "sluttlager" in learned_terms_for_market(shadow, "NO")


def test_promotion_config_requires_explicit_auditable_decision(tmp_path) -> None:
    path = tmp_path / "query-promotions.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "query-promotion-gate-1.0",
                "decisions": [
                    {
                        "market_code": "NO",
                        "term": "sluttlager",
                        "status": "PROMOTED",
                        "reason": "Shadow recovered verified missed opportunity with acceptable precision.",
                        "approved_at": "2026-08-22T10:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    decisions = load_query_promotion_decisions(path)

    assert decisions == {("NO", "sluttlager"): "PROMOTED"}
