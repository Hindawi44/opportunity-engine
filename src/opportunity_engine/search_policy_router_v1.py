"""Review-only search policy recommendations from Unified Memory V2.

The router ranks already-measured Exa queries.  It never executes search,
changes a query pack, allocates money, activates a provider/source, or mutates
production.  Callers must supply the current primary and conditional query
identities so this module does not become a second query-pack source of truth.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    classify_project_domain,
)


SCHEMA_VERSION = "search-policy-router-1.0"
SUPPORTED_MARKETS = ("NO", "SE", "DE", "FR", "IT", "NL")
MIN_CHALLENGE_DAYS = 2
MIN_DEAD_CANDIDATE_DAYS = 3

_SAFETY_FALSE_FIELDS = (
    "automatic_query_activation",
    "automatic_provider_activation",
    "automatic_source_promotion",
    "automatic_code_change",
    "production_query_mutation",
    "production_mutation",
    "automatic_contact",
    "automatic_bid",
    "automatic_reservation",
    "automatic_purchase",
    "automatic_payment",
)


def _text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _upper(value: object) -> str:
    return _text(value).upper()


def _rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _query_sets(
    values: Mapping[str, Sequence[str]] | None,
) -> dict[str, set[str]]:
    output: dict[str, set[str]] = {market: set() for market in SUPPORTED_MARKETS}
    if values is None:
        return output
    for raw_market, queries in values.items():
        market = _upper(raw_market)
        if market not in output:
            raise ValueError(f"unsupported router market: {market or 'MISSING'}")
        for raw_query in queries:
            query = _text(raw_query)
            if not query:
                raise ValueError(f"{market} router query identity is empty")
            output[market].add(query)
    return output


def _validate_memory(memory: Mapping[str, Any]) -> None:
    if not _text(memory.get("schema_version")).startswith("unified-memory-2."):
        raise ValueError("Search Policy Router V1 requires Unified Memory V2")
    if _upper(memory.get("status")) not in {"SUCCESS", "VALID_ZERO"}:
        raise ValueError("Unified Memory V2 must be successful")
    if memory.get("project_domain_gate_enforced") is not True:
        raise ValueError("Unified Memory V2 lost its project-domain gate")
    for field in _SAFETY_FALSE_FIELDS:
        if memory.get(field) is not False:
            raise ValueError(f"Unified Memory V2 changed safety field {field}")


def _runtime_role(
    *,
    market: str,
    query: str,
    primary: Mapping[str, set[str]],
    conditional: Mapping[str, set[str]],
    review: Mapping[str, set[str]],
) -> str:
    if query in primary[market]:
        return "PRIMARY"
    if query in conditional[market]:
        return "CONDITIONAL"
    if query in review[market]:
        return "TRIAL_REVIEW"
    return "HISTORICAL"


def _decision(*, role: str, requests: int, unique: int, days: int) -> tuple[str, str]:
    if requests < 1 or days < 1:
        return "UNKNOWN", "No independent production request evidence is available."
    if unique == 0 and days >= MIN_DEAD_CANDIDATE_DAYS:
        return (
            "HOLD",
            "Zero unique Fresh Exact-Lots across at least three independent checkpoint days; human review is required before any removal.",
        )
    if role == "PRIMARY":
        return "KEEP", "Current primary query remains review-only and budget-neutral."
    if role == "CONDITIONAL":
        if unique > 0:
            return "CONDITIONAL", "Measured optional query remains eligible only behind its existing runtime trigger."
        return "REVIEW", "Conditional query has insufficient positive evidence."
    if role == "TRIAL_REVIEW":
        return (
            "REVIEW",
            "The bounded three-day query challenge is complete; a human must keep or revert it.",
        )
    if unique > 0 and days >= MIN_CHALLENGE_DAYS:
        return "CHALLENGE", "Historical query has enough independent positive evidence for a bounded comparison."
    return "REVIEW", "Historical evidence is not mature enough for a bounded challenge."


def build_search_policy_router_v1(
    memory: Mapping[str, Any],
    *,
    primary_queries: Mapping[str, Sequence[str]],
    conditional_queries: Mapping[str, Sequence[str]] | None = None,
    review_queries: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Build deterministic recommendations without changing runtime behavior."""
    _validate_memory(memory)
    primary = _query_sets(primary_queries)
    conditional = _query_sets(conditional_queries)
    review = _query_sets(review_queries)
    overlap = {
        market: sorted(primary[market] & conditional[market])
        for market in SUPPORTED_MARKETS
        if primary[market] & conditional[market]
    }
    if overlap:
        raise ValueError(f"router query cannot be both primary and conditional: {overlap}")
    review_overlap = {
        market: sorted(
            (primary[market] & review[market])
            | (conditional[market] & review[market])
        )
        for market in SUPPORTED_MARKETS
        if (primary[market] & review[market])
        or (conditional[market] & review[market])
    }
    if review_overlap:
        raise ValueError(f"router review query overlaps an active role: {review_overlap}")

    recommendations: list[dict[str, Any]] = []
    excluded_provider_count = 0
    excluded_out_of_domain_count = 0
    by_market: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _rows(memory.get("query_memory")):
        market = _upper(row.get("market_code"))
        query = _text(row.get("query"))
        provider = _text(row.get("provider")).lower()
        if market not in SUPPORTED_MARKETS or not query:
            continue
        if classify_project_domain(text=query) != CLOTHING_INVENTORY:
            excluded_out_of_domain_count += 1
            continue
        if provider != "exa":
            excluded_provider_count += 1
            continue
        requests = int(row.get("production_search_request_count") or 0)
        unique = int(row.get("unique_fresh_strict_exact_lot_count") or 0)
        days = int(row.get("independent_checkpoint_day_count") or 0)
        yield_per_request = unique / requests if requests else 0.0
        role = _runtime_role(
            market=market,
            query=query,
            primary=primary,
            conditional=conditional,
            review=review,
        )
        decision, reason = _decision(
            role=role,
            requests=requests,
            unique=unique,
            days=days,
        )
        recommendation = {
            "market_code": market,
            "provider": "exa",
            "query": query,
            "runtime_role": role,
            "query_family": (
                next(iter(row.get("query_stage_metrics") or {}), "UNKNOWN")
                if len(row.get("query_stage_metrics") or {}) == 1
                else "MIXED"
            ),
            "path_type": "SEARCH_PROVIDER",
            "provider_or_direct_path": "exa / EXA_EXACT_LOT_MULTIHOP",
            "decision": decision,
            "reason": reason,
            "search_request_count": requests,
            "fresh_strict_exact_lot_count": int(
                row.get("fresh_strict_exact_lot_count") or 0
            ),
            "fresh_candidate_count": None,
            "verified_candidate_count": None,
            "candidate_measurement_status": "UNKNOWN_NOT_RECORDED_IN_QUERY_MEMORY",
            "unique_fresh_strict_exact_lot_count": unique,
            "unique_fresh_yield_per_request": yield_per_request,
            "independent_checkpoint_day_count": days,
            "checkpoint_days": list(row.get("checkpoint_days") or []),
            "freshness": (
                max(row.get("checkpoint_days") or [])
                if row.get("checkpoint_days")
                else None
            ),
            "cost": None,
            "cost_status": "UNKNOWN_NOT_RECORDED_IN_QUERY_MEMORY",
            "request_slots_added": 0,
            "recovery_query_credit": int(row.get("recovery_exact_lot_query_credit") or 0),
            "human_review_required": decision in {"CHALLENGE", "HOLD", "REVIEW", "UNKNOWN"},
        }
        recommendations.append(recommendation)
        by_market[market].append(recommendation)

    market_decisions: dict[str, dict[str, Any]] = {}
    for market in SUPPORTED_MARKETS:
        rows = by_market.get(market, [])
        active = [row for row in rows if row["runtime_role"] == "PRIMARY"]
        trial_reviews = [
            row for row in rows if row["runtime_role"] == "TRIAL_REVIEW"
        ]
        challengers = (
            []
            if trial_reviews
            else [row for row in rows if row["decision"] == "CHALLENGE"]
        )
        weakest = min(
            active,
            key=lambda row: (
                row["unique_fresh_yield_per_request"],
                row["independent_checkpoint_day_count"],
                row["query"],
            ),
            default=None,
        )
        best = max(
            challengers,
            key=lambda row: (
                row["unique_fresh_yield_per_request"],
                row["independent_checkpoint_day_count"],
                row["unique_fresh_strict_exact_lot_count"],
                row["query"],
            ),
            default=None,
        )
        challenge_available = bool(
            weakest
            and best
            and best["unique_fresh_yield_per_request"]
            > weakest["unique_fresh_yield_per_request"]
        )
        market_decisions[market] = {
            "decision": "CHALLENGE_AVAILABLE" if challenge_available else "KEEP_OR_REVIEW",
            "weakest_primary_query": weakest["query"] if weakest else None,
            "weakest_primary_unique_yield_per_request": (
                weakest["unique_fresh_yield_per_request"] if weakest else None
            ),
            "best_challenger_query": best["query"] if challenge_available else None,
            "best_challenger_unique_yield_per_request": (
                best["unique_fresh_yield_per_request"] if challenge_available else None
            ),
            "request_slots_added": 0,
            "human_review_required": challenge_available
            or any(row["decision"] in {"HOLD", "REVIEW", "UNKNOWN"} for row in rows),
        }

    recommendations.sort(
        key=lambda row: (
            row["market_code"],
            {
                "PRIMARY": 0,
                "CONDITIONAL": 1,
                "TRIAL_REVIEW": 2,
                "HISTORICAL": 3,
            }[row["runtime_role"]],
            row["query"],
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS" if recommendations else "VALID_ZERO",
        "mode": "REVIEW_ONLY",
        "provider_scope": "EXA_EXACT_LOT_ONLY",
        "market_coverage": list(SUPPORTED_MARKETS),
        "recommendation_count": len(recommendations),
        "recommendations": recommendations,
        "market_decisions": market_decisions,
        "excluded_non_exa_query_count": excluded_provider_count,
        "excluded_out_of_domain_query_count": excluded_out_of_domain_count,
        "budget_policy": "SUBSTITUTE_WITHIN_EXISTING_REQUEST_SLOTS_ONLY",
        "request_slots_added": 0,
        "cost": None,
        "cost_status": "UNKNOWN_NOT_RECORDED_IN_QUERY_MEMORY",
        "automatic_query_activation": False,
        "automatic_provider_activation": False,
        "automatic_source_promotion": False,
        "automatic_code_change": False,
        "production_query_mutation": False,
        "production_mutation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
