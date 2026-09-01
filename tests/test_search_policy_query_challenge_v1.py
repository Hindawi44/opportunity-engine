from __future__ import annotations

from opportunity_engine.search_policy_query_challenge_v1 import (
    CHALLENGES,
    POLICY_CHALLENGE_STAGE,
    build_market_query_plan,
)


BASE_QUERIES = {
    "DE": (
        CHALLENGES["DE"]["incumbent_query"],
        "Deutschland Bekleidung Restposten Großhandel Sonderposten Preis Menge Stück",
    ),
    "NO": (
        "Norge klær vareparti nettauksjon konkursbo lager pris antall stk",
        CHALLENGES["NO"]["incumbent_query"],
    ),
    "FR": ("France liquidation judiciaire vêtements stock lot à vendre",),
}


def _metric(*, days: list[str], requests: int, raw: int, unique: int) -> dict:
    return {
        "checkpoint_days": days,
        "independent_checkpoint_day_count": len(days),
        "search_request_count": requests,
        "fresh_strict_exact_lot_count": raw,
        "unique_fresh_strict_exact_lot_count": unique,
    }


def _memory(*, market: str, challenge_days: list[str]) -> dict:
    config = CHALLENGES[market]
    return {
        "schema_version": "unified-memory-2.0",
        "status": "SUCCESS",
        "project_domain_gate_enforced": True,
        "query_memory": [
            {
                "market_code": market,
                "provider": "exa",
                "query": config["incumbent_query"],
                "query_stage_metrics": {
                    "PRIMARY": _metric(
                        days=["2026-08-31", "2026-09-01"],
                        requests=2,
                        raw=2,
                        unique=1,
                    )
                },
            },
            {
                "market_code": market,
                "provider": "exa",
                "query": config["challenger_query"],
                "query_stage_metrics": {
                    "PRIMARY": _metric(
                        days=["2026-08-28", "2026-08-29", "2026-08-30"],
                        requests=3,
                        raw=30,
                        unique=10,
                    ),
                    POLICY_CHALLENGE_STAGE: _metric(
                        days=challenge_days,
                        requests=len(challenge_days),
                        raw=6 * len(challenge_days),
                        unique=4 * len(challenge_days),
                    ),
                },
            },
        ],
    }


def test_de_challenge_replaces_one_existing_slot_only() -> None:
    plan, state = build_market_query_plan(
        market="DE",
        base_queries=BASE_QUERIES["DE"],
        memory=_memory(market="DE", challenge_days=[]),
        observation_day="2026-09-02",
    )

    assert tuple(row["query"] for row in plan) == (
        CHALLENGES["DE"]["challenger_query"],
        BASE_QUERIES["DE"][1],
    )
    assert plan[0]["query_stage"] == POLICY_CHALLENGE_STAGE
    assert state["status"] == "ACTIVE"
    assert state["request_slots_before"] == 2
    assert state["request_slots_after"] == 2
    assert state["request_slots_added"] == 0
    assert state["budget_change"] == 0


def test_no_challenge_uses_the_weak_second_slot() -> None:
    plan, state = build_market_query_plan(
        market="NO",
        base_queries=BASE_QUERIES["NO"],
        memory=_memory(market="NO", challenge_days=[]),
        observation_day="2026-09-02",
    )

    assert tuple(row["query"] for row in plan) == (
        BASE_QUERIES["NO"][0],
        CHALLENGES["NO"]["challenger_query"],
    )
    assert plan[1]["query_stage"] == POLICY_CHALLENGE_STAGE
    assert state["status"] == "ACTIVE"


def test_challenge_stays_active_until_three_independent_days() -> None:
    plan, state = build_market_query_plan(
        market="DE",
        base_queries=BASE_QUERIES["DE"],
        memory=_memory(
            market="DE",
            challenge_days=["2026-09-02", "2026-09-03"],
        ),
        observation_day="2026-09-04",
    )

    assert plan[0]["query"] == CHALLENGES["DE"]["challenger_query"]
    assert state["status"] == "ACTIVE"
    assert state["completed_independent_checkpoint_days"] == 2
    assert state["remaining_independent_checkpoint_days"] == 1
    assert state["expected_completed_days_after_successful_new_day"] == 3


def test_challenge_does_not_repeat_on_the_same_day() -> None:
    plan, state = build_market_query_plan(
        market="NO",
        base_queries=BASE_QUERIES["NO"],
        memory=_memory(market="NO", challenge_days=["2026-09-02"]),
        observation_day="2026-09-02",
    )

    assert tuple(row["query"] for row in plan) == BASE_QUERIES["NO"]
    assert state["status"] == "PAUSED_ALREADY_OBSERVED_TODAY"
    assert state["completed_independent_checkpoint_days"] == 1


def test_challenge_expires_after_three_days_and_requires_human_review() -> None:
    plan, state = build_market_query_plan(
        market="DE",
        base_queries=BASE_QUERIES["DE"],
        memory=_memory(
            market="DE",
            challenge_days=["2026-09-02", "2026-09-03", "2026-09-04"],
        ),
        observation_day="2026-09-05",
    )

    assert tuple(row["query"] for row in plan) == BASE_QUERIES["DE"]
    assert state["status"] == "COMPLETED_REVIEW_REQUIRED"
    assert state["remaining_independent_checkpoint_days"] == 0
    assert state["automatic_expiry"] is True
    assert state["human_review_required"] is True
    assert state["review_proposal"] == "KEEP_CHALLENGER_FOR_HUMAN_REVIEW"


def test_missing_memory_pauses_instead_of_mutating_the_pack() -> None:
    plan, state = build_market_query_plan(
        market="DE",
        base_queries=BASE_QUERIES["DE"],
        memory=None,
        observation_day="2026-09-02",
    )

    assert tuple(row["query"] for row in plan) == BASE_QUERIES["DE"]
    assert state["status"] == "PAUSED_MEMORY_UNAVAILABLE"


def test_unselected_markets_remain_unchanged() -> None:
    plan, state = build_market_query_plan(
        market="FR",
        base_queries=BASE_QUERIES["FR"],
        memory=_memory(market="DE", challenge_days=[]),
        observation_day="2026-09-02",
    )

    assert tuple(row["query"] for row in plan) == BASE_QUERIES["FR"]
    assert tuple(row["query_stage"] for row in plan) == ("PRIMARY",)
    assert state["status"] == "NOT_APPLICABLE"
    assert state["request_slots_added"] == 0

