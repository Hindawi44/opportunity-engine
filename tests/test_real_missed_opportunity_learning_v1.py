from __future__ import annotations

import json
from datetime import datetime, timezone

from opportunity_engine.adaptive_keyword_learning import propose_query_gap_keywords
from opportunity_engine.daily_learning_operator import run_daily_learning_cycle
from opportunity_engine.daily_learning_runtime import _learning_query, run_daily_learning_runtime
from opportunity_engine.learned_query_overlay import learned_terms_for_market
from opportunity_engine.missed_opportunity_learning import DiscoveryTrace, MissedOpportunityCase


LENE_INTERIOR_URL = (
    "https://www.stavangersentrum.no/nyheter/"
    "15-fantastiske-ar-og-en-varm-takk-til-stavanger"
)
NOREM_BAADE_URL = "https://www.aftenbladet.no/lokalt/i/lrb8o/slutt-for-norem-baade"


def _real_lene_interior_miss() -> MissedOpportunityCase:
    return MissedOpportunityCase(
        case_id="REAL-MISS-NO-LENE-INTERIOR-2025-08",
        market_code="NO",
        discovered_by="HUMAN_VERIFIED_PUBLIC_SOURCE",
        observed_at=datetime(2025, 8, 28, tzinfo=timezone.utc),
        opportunity_type="STORE_CLOSURE_STOCK_LIQUIDATION",
        stock_proven=True,
        ground_truth_company="Lene Interiør",
        ground_truth_url=LENE_INTERIOR_URL,
        trace=DiscoveryTrace(query_generated=False),
        learning_evidence_text=(
            "Lene Interiør legges ned. Stort avslutningssalg på alle varer i butikken."
        ),
    ).with_diagnosis()


def _hidden_norem_baade_holdout() -> MissedOpportunityCase:
    return MissedOpportunityCase(
        case_id="HOLDOUT-NO-NOREM-BAADE-2010",
        market_code="NO",
        discovered_by="HIDDEN_VALIDATION_PUBLIC_SOURCE",
        observed_at=datetime(2010, 11, 12, tzinfo=timezone.utc),
        opportunity_type="STORE_CLOSURE_STOCK_LIQUIDATION",
        stock_proven=True,
        ground_truth_company="Norem Baade",
        ground_truth_url=NOREM_BAADE_URL,
        trace=DiscoveryTrace(),
        learning_evidence_text="",
        root_cause="VALIDATION_HOLDOUT",
        learning_status="HOLDOUT",
    )


def _baseline_queries() -> list[str]:
    return [
        '("opphørssalg" OR "avviklingssalg" OR "konkurssalg" OR konkurs) klær',
        '("restlager" OR "varelager" OR "lagersalg") salg',
    ]


def _verified_replay_search(term: str, market_code: str):
    assert market_code == "NO"
    if term != "avslutningssalg":
        return []
    return [
        {
            "company": "Lene Interiør",
            "url": LENE_INTERIOR_URL,
            "verified_relevant": True,
        },
        {
            "company": "Ordinary seasonal sale",
            "url": "https://noise.example/seasonal-sale",
        },
    ]


def _hidden_transfer_search(term: str, market_code: str):
    assert market_code == "NO"
    if term == "avslutningssalg":
        return [
            {"title": "Unrelated avslutningssalg", "url": "https://noise.example/a"},
            {"title": "Another sale", "url": "https://noise.example/b"},
        ]
    if term == "stort avslutningssalg":
        return [
            {
                "title": "Slutt for Norem Baade",
                "url": NOREM_BAADE_URL,
            },
            {"title": "Unrelated closing sale", "url": "https://noise.example/c"},
        ]
    return []


def test_real_miss_proposes_avslutningssalg_as_query_gap() -> None:
    case = _real_lene_interior_miss()

    candidates = propose_query_gap_keywords([case], active_queries=_baseline_queries())
    by_term = {candidate.term: candidate for candidate in candidates}

    assert case.root_cause == "QUERY_GAP"
    assert "avslutningssalg" in by_term
    assert by_term["avslutningssalg"].support_case_ids == (case.case_id,)


def test_generalizable_atomic_term_is_prioritized_without_invented_adjacency() -> None:
    candidates = propose_query_gap_keywords(
        [_real_lene_interior_miss()],
        active_queries=_baseline_queries(),
    )
    terms = [candidate.term for candidate in candidates]

    assert terms[:2] == ["avslutningssalg", "stort avslutningssalg"]
    assert "avslutningssalg alle" not in terms


def test_direct_replay_behavior_remains_supported() -> None:
    case = _real_lene_interior_miss()

    outcome = run_daily_learning_cycle(
        existing_cases=[case],
        inbox_cases=[],
        active_queries=_baseline_queries(),
        search=_verified_replay_search,
    )

    shadow_terms = learned_terms_for_market(outcome.shadow_overlay, "NO")
    active_terms = learned_terms_for_market(outcome.overlay, "NO")
    learned_case = next(item for item in outcome.cases if item.case_id == case.case_id)

    assert "avslutningssalg" in shadow_terms
    assert "avslutningssalg" not in active_terms
    assert learned_case.learning_status == "RECOVERED"
    assert outcome.report["recovered_case_count"] == 1
    assert outcome.report["transfer_proven_case_count"] == 0
    assert outcome.report["automatic_query_activation"] is False


def test_real_miss_can_generalize_to_hidden_holdout_without_production_activation() -> None:
    miss = _real_lene_interior_miss()
    holdout = _hidden_norem_baade_holdout()

    outcome = run_daily_learning_cycle(
        existing_cases=[miss],
        inbox_cases=[],
        validation_cases=[holdout],
        active_queries=_baseline_queries(),
        search=_hidden_transfer_search,
    )

    shadow_terms = learned_terms_for_market(outcome.shadow_overlay, "NO")
    active_terms = learned_terms_for_market(outcome.overlay, "NO")
    learned_case = next(item for item in outcome.cases if item.case_id == miss.case_id)
    phrase_eval = next(
        item for item in outcome.evaluations if item.term == "stort avslutningssalg"
    )

    assert phrase_eval.status == "PROVEN"
    assert phrase_eval.evaluation_scope == "HOLDOUT_TRANSFER"
    assert phrase_eval.support_case_ids == (miss.case_id,)
    assert phrase_eval.recovered_case_ids == (holdout.case_id,)
    assert phrase_eval.precision == 0.5
    assert "stort avslutningssalg" in shadow_terms
    assert active_terms == {}
    assert learned_case.learning_status == "TRANSFER_PROVEN"
    assert "stort avslutningssalg" in learned_case.learned_patterns
    assert outcome.report["validation_case_count"] == 1
    assert outcome.report["transfer_proven_case_count"] == 1
    assert outcome.report["recovered_case_count"] == 0
    assert outcome.report["active_learned_term_count"] == 0
    assert outcome.report["promotion_gate_enforced"] is True


def test_learning_search_replays_term_without_product_or_company_leakage() -> None:
    query = _learning_query("avslutningssalg")

    assert query == '"avslutningssalg"'
    assert "lene" not in query.casefold()
    assert "norem" not in query.casefold()
    assert "klær" not in query.casefold()
    assert "elektronikk" not in query.casefold()
    assert "interiør" not in query.casefold()


def test_real_miss_runs_end_to_end_through_persistent_holdout_runtime(tmp_path) -> None:
    learning_dir = tmp_path / "learning"
    inbox = tmp_path / "missed-opportunity-inbox.json"
    validation = tmp_path / "query-gap-validation-cases.json"
    active_queries = tmp_path / "active-queries.json"
    promotions = tmp_path / "query-promotions.json"
    report_path = tmp_path / "daily-learning-cycle.json"

    inbox.write_text(
        json.dumps(
            {
                "schema_version": "missed-opportunity-inbox-1.0",
                "cases": [_real_lene_interior_miss().to_dict()],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    validation.write_text(
        json.dumps(
            {
                "schema_version": "query-gap-validation-cases-1.0",
                "cases": [_hidden_norem_baade_holdout().to_dict()],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    active_queries.write_text('{"queries": []}', encoding="utf-8")
    promotions.write_text(
        '{"schema_version":"query-promotion-gate-1.0","decisions":[]}',
        encoding="utf-8",
    )

    report = run_daily_learning_runtime(
        learning_dir=learning_dir,
        inbox_path=inbox,
        validation_cases_path=validation,
        active_query_config=active_queries,
        promotion_config_path=promotions,
        report_path=report_path,
        search_override=_hidden_transfer_search,
        observed_at=datetime(2026, 8, 22, 14, 45, tzinfo=timezone.utc),
    )

    shadow_payload = json.loads(
        (learning_dir / "shadow-keyword-overlay.json").read_text(encoding="utf-8")
    )
    active_payload = json.loads(
        (learning_dir / "active-keyword-overlay.json").read_text(encoding="utf-8")
    )
    memory_payload = json.loads(
        (learning_dir / "missed-opportunities.json").read_text(encoding="utf-8")
    )
    proof = json.loads(
        (learning_dir / "safe-learning-proof.json").read_text(encoding="utf-8")
    )

    assert report["known_missed_opportunity_count"] == 1
    assert report["validation_case_count"] == 1
    assert report["proven_term_count_this_run"] == 1
    assert report["recovered_case_count"] == 0
    assert report["transfer_proven_case_count"] == 1
    assert report["shadow_proven_term_count"] >= 1
    assert report["active_learned_term_count"] == 0
    assert report["automatic_query_activation"] is False
    assert report["promotion_gate_enforced"] is True

    assert "stort avslutningssalg" in learned_terms_for_market(shadow_payload, "NO")
    assert learned_terms_for_market(active_payload, "NO") == {}
    assert memory_payload["cases"][0]["learning_status"] == "TRANSFER_PROVEN"
    assert proof["status"] == "SHADOW_PASSED"
    assert proof["shadow_recovered_case_count"] == 0
    assert proof["shadow_transfer_proven_case_count"] == 1
    assert proof["promotion_eligible_count"] == 1
    assert proof["promoted_proof_count"] == 0
    assert proof["automatic_promotion"] is False
    proof_case = proof["cases"][0]
    assert proof_case["shadow_transfer_proven"] is True
    assert proof_case["shadow_validation_case_ids"] == ["HOLDOUT-NO-NOREM-BAADE-2010"]
