from __future__ import annotations

import pytest

from opportunity_engine.production_search_outcome_history_seed_compact_v1 import (
    load_compact_historical_query_outcome_seed,
)
from opportunity_engine.production_search_outcome_history_seed_v1 import (
    augment_unified_learning_spine_with_history,
    install_historical_query_outcome_memory_metrics,
)
from opportunity_engine.search_policy_router_v1 import build_search_policy_router_v1
from opportunity_engine.unified_learning_spine import build_unified_learning_spine
from opportunity_engine.unified_memory_v2 import build_unified_memory_v2


PRIMARY = {
    "NO": (
        "Norge klær vareparti nettauksjon konkursbo lager pris antall stk",
        "Norge arbeidsklær overskuddsvarer auksjon høyeste bud stk",
    ),
    "SE": (
        "Sverige restparti kläder grossist lager",
        "Sverige överskottslager kläder till salu parti",
        "Sverige kläder varulager auktion parti pris antal plagg",
    ),
    "DE": (
        "Deutschland Lagerware Bekleidung Mindestabnahme angebotene Menge Nettopreis Stück",
        "Deutschland Bekleidung Restposten Großhandel Sonderposten Preis Menge Stück",
    ),
    "FR": (
        "France liquidation judiciaire vêtements stock lot à vendre vente aux enchères prix quantité pièces disponible",
    ),
    "IT": (
        "Italia abbigliamento moda lotto stock in vendita prezzo pezzi magazzino disponibile",
    ),
    "NL": (
        "Nederland kleding groothandel partij pakket pallet te koop prijs stuks voorraad",
    ),
}

CONDITIONAL = {
    "SE": ("Sverige restpartier kläder grossist säljes parti",),
    "FR": (
        "France déstockage vêtements grossiste stock lot",
        "France vêtements clothing Jack & Jones déstockage grossiste stock lot à vendre",
        "France vêtements clothing Pronovias déstockage grossiste stock lot à vendre",
    ),
    "IT": (
        "Italia liquidazione stock abbigliamento ingrosso",
        "Italia abbigliamento clothing Jack & Jones stock lotto ingrosso in vendita",
        "Italia abbigliamento clothing Pronovias stock lotto ingrosso in vendita",
    ),
    "NL": (
        "Nederland kledingvoorraad restpartij groothandel",
        "Nederland kleding clothing Jack & Jones restpartij groothandel voorraad te koop",
        "Nederland kleding clothing Pronovias restpartij groothandel voorraad te koop",
    ),
}


def _memory() -> dict:
    install_historical_query_outcome_memory_metrics()
    spine = build_unified_learning_spine(
        unified_intelligence_items=None,
        search_success_memory=None,
        missed_opportunity_memory=None,
        daily_learning=None,
    )
    spine["generated_at"] = "2026-09-02T08:00:00+00:00"
    complete_live_bridge = {
        "schema_version": "production-search-outcome-bridge-1.0",
        "status": "SUCCESS",
        "project_domain": "CLOTHING_INVENTORY",
        "provider": "exa",
        "market_coverage": ["NO", "SE", "DE", "FR", "IT", "NL"],
        "market_status": {
            market: {
                "status": "SUCCESS",
                "resolution": True,
                "candidates": True,
                "search_report": True,
            }
            for market in ("NO", "SE", "DE", "FR", "IT", "NL")
        },
        "records": [],
        "recovery_query_credit_blocked": True,
    }
    spine = augment_unified_learning_spine_with_history(
        spine,
        load_compact_historical_query_outcome_seed(),
        live_bridge=complete_live_bridge,
    )
    return build_unified_memory_v2(
        existing_memory=None,
        unified_learning_spine=spine,
        run_id="router-history-test",
        rule_registry={},
    )


def _recommendation(router: dict, *, market: str, query: str) -> dict:
    return next(
        row
        for row in router["recommendations"]
        if row["market_code"] == market and row["query"] == query
    )


def test_router_uses_unique_yield_and_surfaces_german_challenger() -> None:
    router = build_search_policy_router_v1(
        _memory(), primary_queries=PRIMARY, conditional_queries=CONDITIONAL
    )

    decision = router["market_decisions"]["DE"]
    assert decision["decision"] == "CHALLENGE_AVAILABLE"
    assert decision["best_challenger_query"] == (
        "Deutschland Restposten Bekleidung Großhandel Lager"
    )
    assert decision["best_challenger_unique_yield_per_request"] == pytest.approx(23 / 3)
    assert decision["weakest_primary_unique_yield_per_request"] == pytest.approx(1 / 2)
    assert decision["request_slots_added"] == 0


def test_router_holds_repeated_zero_but_never_mutates_query_pack() -> None:
    router = build_search_policy_router_v1(
        _memory(), primary_queries=PRIMARY, conditional_queries=CONDITIONAL
    )
    recall = _recommendation(
        router,
        market="SE",
        query="Sverige restpartier kläder grossist säljes parti",
    )

    assert recall["runtime_role"] == "CONDITIONAL"
    assert recall["decision"] == "HOLD"
    assert recall["unique_fresh_strict_exact_lot_count"] == 0
    assert recall["independent_checkpoint_day_count"] == 4
    assert recall["human_review_required"] is True
    assert router["request_slots_added"] == 0
    assert router["production_query_mutation"] is False
    assert router["automatic_query_activation"] is False


def test_router_keeps_recovery_credit_zero_and_cost_unknown() -> None:
    router = build_search_policy_router_v1(
        _memory(), primary_queries=PRIMARY, conditional_queries=CONDITIONAL
    )

    assert router["cost"] is None
    assert router["cost_status"] == "UNKNOWN_NOT_RECORDED_IN_QUERY_MEMORY"
    assert all(row["recovery_query_credit"] == 0 for row in router["recommendations"])
    assert router["provider_scope"] == "EXA_EXACT_LOT_ONLY"


def test_completed_bounded_challenger_is_held_for_human_review() -> None:
    challenger = "Deutschland Restposten Bekleidung Großhandel Lager"
    router = build_search_policy_router_v1(
        _memory(),
        primary_queries=PRIMARY,
        conditional_queries=CONDITIONAL,
        review_queries={"DE": (challenger,)},
    )

    row = _recommendation(router, market="DE", query=challenger)
    assert row["runtime_role"] == "TRIAL_REVIEW"
    assert row["decision"] == "REVIEW"
    assert row["human_review_required"] is True
    assert router["market_decisions"]["DE"]["decision"] == "KEEP_OR_REVIEW"


def test_router_excludes_out_of_domain_query_memory() -> None:
    memory = _memory()
    memory["query_memory"].append(
        {
            "market_code": "NL",
            "provider": "exa",
            "query": "FABRIC_PROCUREMENT Nederland stoffen groothandel leveranciers catalogus",
            "production_search_request_count": 3,
            "fresh_strict_exact_lot_count": 8,
            "unique_fresh_strict_exact_lot_count": 8,
            "independent_checkpoint_day_count": 3,
        }
    )

    router = build_search_policy_router_v1(
        memory, primary_queries=PRIMARY, conditional_queries=CONDITIONAL
    )

    assert router["excluded_out_of_domain_query_count"] == 1
    assert all(
        "FABRIC_PROCUREMENT" not in row["query"]
        for row in router["recommendations"]
    )


def test_router_fails_closed_on_unsafe_or_overlapping_input() -> None:
    unsafe = _memory()
    unsafe["production_mutation"] = True
    with pytest.raises(ValueError, match="production_mutation"):
        build_search_policy_router_v1(
            unsafe, primary_queries=PRIMARY, conditional_queries=CONDITIONAL
        )

    with pytest.raises(ValueError, match="both primary and conditional"):
        build_search_policy_router_v1(
            _memory(),
            primary_queries={"NO": ("same query",)},
            conditional_queries={"NO": ("same query",)},
        )
