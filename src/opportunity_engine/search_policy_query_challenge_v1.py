"""Human-approved, one-for-one Search Policy query challenges.

The challenge controller is deliberately small and fail-closed.  It may replace
one existing Exa primary query with one reviewed challenger, but it cannot add a
request slot, change provider, or continue beyond three independent checkpoint
days.  Unified Memory V2 is the counter; the dedicated ``POLICY_CHALLENGE``
query stage keeps new trial evidence separate from older production history.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "search-policy-query-challenge-1.0"
POLICY_CHALLENGE_STAGE = "POLICY_CHALLENGE"
MAX_INDEPENDENT_CHECKPOINT_DAYS = 3

CHALLENGES: dict[str, dict[str, Any]] = {
    "DE": {
        "trial_id": "SEARCH_POLICY_DE_PRIMARY_SLOT_1_V1",
        "incumbent_query": (
            "Deutschland Lagerware Bekleidung Mindestabnahme angebotene Menge "
            "Nettopreis Stück"
        ),
        "challenger_query": "Deutschland Restposten Bekleidung Großhandel Lager",
    },
    "NO": {
        "trial_id": "SEARCH_POLICY_NO_PRIMARY_SLOT_2_V1",
        "incumbent_query": "Norge arbeidsklær overskuddsvarer auksjon høyeste bud stk",
        "challenger_query": (
            "Norge klær vareparti nettauksjon auksjon plagg til salgs pris stk"
        ),
    },
}

# Human decision recorded after the bounded 2026-09-02..2026-09-04 trial.
# Germany's challenger produced 20 unique fresh strict Exact-Lots from three
# requests versus one for the incumbent. Norway tied the incumbent at one
# unique result, so the incumbent remains in production.  These decisions do
# not add request slots or change provider/budget.
FINALIZED_CHALLENGE_DECISIONS: dict[str, str] = {
    "DE": "KEEP_CHALLENGER",
    "NO": "REVERT_INCUMBENT",
}


def _text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _upper(value: object) -> str:
    return _text(value).upper()


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _memory_available(memory: Mapping[str, Any] | None) -> bool:
    payload = _mapping(memory)
    return bool(
        _text(payload.get("schema_version")).startswith("unified-memory-2.")
        and _upper(payload.get("status")) in {"SUCCESS", "VALID_ZERO"}
        and payload.get("project_domain_gate_enforced") is True
    )


def _stage_metric(
    memory: Mapping[str, Any] | None,
    *,
    market: str,
    query: str,
    stage: str,
) -> dict[str, Any]:
    for row in _rows(_mapping(memory).get("query_memory")):
        if _upper(row.get("market_code")) != market:
            continue
        if _text(row.get("provider")).casefold() != "exa":
            continue
        if _text(row.get("query")) != query:
            continue
        metric = _mapping(_mapping(row.get("query_stage_metrics")).get(stage))
        days = sorted({_text(day) for day in metric.get("checkpoint_days") or [] if _text(day)})
        recorded_day_count = int(metric.get("independent_checkpoint_day_count") or 0)
        day_count = max(len(days), recorded_day_count)
        requests = int(metric.get("search_request_count") or 0)
        unique = int(metric.get("unique_fresh_strict_exact_lot_count") or 0)
        raw = int(metric.get("fresh_strict_exact_lot_count") or 0)
        return {
            "search_request_count": requests,
            "independent_checkpoint_day_count": day_count,
            "checkpoint_days": days,
            "fresh_strict_exact_lot_count": raw,
            "unique_fresh_strict_exact_lot_count": unique,
            "unique_fresh_yield_per_request": unique / requests if requests else 0.0,
        }
    return {
        "search_request_count": 0,
        "independent_checkpoint_day_count": 0,
        "checkpoint_days": [],
        "fresh_strict_exact_lot_count": 0,
        "unique_fresh_strict_exact_lot_count": 0,
        "unique_fresh_yield_per_request": 0.0,
    }


def _review_proposal(
    *,
    status: str,
    incumbent: Mapping[str, Any],
    challenger: Mapping[str, Any],
) -> str | None:
    if status != "COMPLETED_REVIEW_REQUIRED":
        return None
    if int(challenger.get("independent_checkpoint_day_count") or 0) < (
        MAX_INDEPENDENT_CHECKPOINT_DAYS
    ):
        return "INSUFFICIENT_TRIAL_EVIDENCE"
    if float(challenger.get("unique_fresh_yield_per_request") or 0.0) > float(
        incumbent.get("unique_fresh_yield_per_request") or 0.0
    ):
        return "KEEP_CHALLENGER_FOR_HUMAN_REVIEW"
    return "REVERT_INCUMBENT_FOR_HUMAN_REVIEW"


def build_market_query_plan(
    *,
    market: str,
    base_queries: Sequence[str],
    memory: Mapping[str, Any] | None,
    observation_day: str | None = None,
) -> tuple[tuple[dict[str, Any], ...], dict[str, Any]]:
    """Return the active primary-slot plan and its bounded challenge state."""
    market_code = _upper(market)
    queries = tuple(_text(query) for query in base_queries if _text(query))
    if len(queries) != len(tuple(base_queries)) or len(set(queries)) != len(queries):
        raise ValueError(f"{market_code} base query pack contains blank or duplicate queries")

    challenge = CHALLENGES.get(market_code)
    if challenge is None:
        plan = tuple(
            {"query": query, "query_stage": "PRIMARY", "trial_id": None}
            for query in queries
        )
        return plan, {
            "schema_version": SCHEMA_VERSION,
            "market_code": market_code,
            "status": "NOT_APPLICABLE",
            "request_slots_before": len(queries),
            "request_slots_after": len(plan),
            "request_slots_added": 0,
            "provider": "exa",
            "automatic_query_activation": False,
            "production_query_mutation": False,
            "production_mutation": False,
        }

    finalized_decision = FINALIZED_CHALLENGE_DECISIONS.get(market_code)
    if finalized_decision:
        incumbent_query = _text(challenge["incumbent_query"])
        challenger_query = _text(challenge["challenger_query"])
        selected_query = (
            challenger_query
            if finalized_decision == "KEEP_CHALLENGER"
            else incumbent_query
        )
        if queries.count(selected_query) != 1:
            raise ValueError(
                f"{market_code} finalized challenge query must occupy exactly one base request slot"
            )
        plan = tuple(
            {"query": query, "query_stage": "PRIMARY", "trial_id": None}
            for query in queries
        )
        return plan, {
            "schema_version": SCHEMA_VERSION,
            "trial_id": challenge["trial_id"],
            "market_code": market_code,
            "status": "HUMAN_DECISION_APPLIED",
            "finalized_decision": finalized_decision,
            "selected_query": selected_query,
            "incumbent_query": incumbent_query,
            "challenger_query": challenger_query,
            "remaining_independent_checkpoint_days": 0,
            "request_slots_before": len(queries),
            "request_slots_after": len(plan),
            "request_slots_added": 0,
            "provider": "exa",
            "budget_change": 0,
            "automatic_expiry": True,
            "human_review_required": False,
            "human_approved_query_substitution": True,
            "human_decision_applied": True,
            "automatic_query_activation": False,
            "production_query_mutation": False,
            "production_mutation": False,
        }

    incumbent_query = _text(challenge["incumbent_query"])
    challenger_query = _text(challenge["challenger_query"])
    if queries.count(incumbent_query) != 1:
        raise ValueError(
            f"{market_code} challenge incumbent must occupy exactly one base request slot"
        )
    if challenger_query in queries:
        raise ValueError(f"{market_code} challenger already occupies a base request slot")

    today = _text(observation_day) or datetime.now(timezone.utc).date().isoformat()
    incumbent_metric = _stage_metric(
        memory,
        market=market_code,
        query=incumbent_query,
        stage="PRIMARY",
    )
    challenger_metric = _stage_metric(
        memory,
        market=market_code,
        query=challenger_query,
        stage=POLICY_CHALLENGE_STAGE,
    )
    completed_days = int(challenger_metric["independent_checkpoint_day_count"])
    observed_days = set(challenger_metric["checkpoint_days"])

    if not _memory_available(memory):
        status = "PAUSED_MEMORY_UNAVAILABLE"
    elif completed_days >= MAX_INDEPENDENT_CHECKPOINT_DAYS:
        status = "COMPLETED_REVIEW_REQUIRED"
    elif today in observed_days:
        status = "PAUSED_ALREADY_OBSERVED_TODAY"
    else:
        status = "ACTIVE"

    active = status == "ACTIVE"
    plan_rows: list[dict[str, Any]] = []
    for query in queries:
        if active and query == incumbent_query:
            plan_rows.append(
                {
                    "query": challenger_query,
                    "query_stage": POLICY_CHALLENGE_STAGE,
                    "trial_id": challenge["trial_id"],
                }
            )
        else:
            plan_rows.append(
                {"query": query, "query_stage": "PRIMARY", "trial_id": None}
            )
    plan = tuple(plan_rows)
    if len(plan) != len(queries):
        raise RuntimeError(f"{market_code} challenge changed the request-slot count")

    state = {
        "schema_version": SCHEMA_VERSION,
        "trial_id": challenge["trial_id"],
        "market_code": market_code,
        "status": status,
        "query_stage": POLICY_CHALLENGE_STAGE,
        "incumbent_query": incumbent_query,
        "challenger_query": challenger_query,
        "observation_day": today,
        "completed_independent_checkpoint_days": completed_days,
        "max_independent_checkpoint_days": MAX_INDEPENDENT_CHECKPOINT_DAYS,
        "remaining_independent_checkpoint_days": max(
            0, MAX_INDEPENDENT_CHECKPOINT_DAYS - completed_days
        ),
        "expected_completed_days_after_successful_new_day": (
            min(MAX_INDEPENDENT_CHECKPOINT_DAYS, completed_days + 1)
            if active
            else completed_days
        ),
        "incumbent_baseline": incumbent_metric,
        "challenger_trial": challenger_metric,
        "review_proposal": _review_proposal(
            status=status,
            incumbent=incumbent_metric,
            challenger=challenger_metric,
        ),
        "request_slots_before": len(queries),
        "request_slots_after": len(plan),
        "request_slots_added": 0,
        "provider": "exa",
        "budget_change": 0,
        "automatic_expiry": True,
        "human_review_required": status == "COMPLETED_REVIEW_REQUIRED",
        "human_approved_query_substitution": True,
        "automatic_query_activation": False,
        "production_query_mutation": False,
        "production_mutation": False,
    }
    return plan, state
