"""Single-provider route replication learning for strict Exact-Lot evidence.

Tool comparison and route replication answer different questions:

* Tool comparison asks whether Exa or Brave is better and therefore requires
  symmetric evidence from both providers.
* Route replication asks whether a previously observed provider/market/query/
  navigation path independently reaches strict Exact-Lot pages again.

This module implements only the second question. It never declares a provider
leader and never activates a provider or mutates production queries.
"""
from __future__ import annotations

from typing import Any, Mapping

from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY
from opportunity_engine.search_success_learning import (
    SCHEMA_VERSION,
    _compact,
    _group_routes,
    _search_hit_count,
    _strict_child_rows,
    _strict_direct_rows,
    _utc_text,
    _validate_benchmark,
    _validate_child_provider,
    _validate_provider_verification,
)

OBSERVATION_SCOPE = "SINGLE_PROVIDER_ROUTE_REPLICATION"
_SUPPORTED_ROUTE_PROVIDERS = frozenset({"exa"})


def build_provider_route_success_observation(
    *,
    run_id: str,
    provider: str,
    benchmark: Mapping[str, Any],
    provider_verification: Mapping[str, Any],
    child_resolution: Mapping[str, Any],
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Build one strict provider-specific route-replication observation.

    This report deliberately carries the same search-success schema used by the
    shared memory updater, but provider comparison fields are explicitly marked
    NOT_EVALUATED so single-provider evidence can never masquerade as a tool win.
    """
    run = _compact(run_id)
    if not run:
        raise ValueError("run_id is required")
    normalized_provider = _compact(provider).casefold()
    if normalized_provider not in _SUPPORTED_ROUTE_PROVIDERS:
        raise ValueError("provider route replication currently supports exa only")

    _validate_benchmark(benchmark)
    if _compact(benchmark.get("provider_mode")).casefold() != normalized_provider:
        raise ValueError(f"provider route replication requires provider_mode={normalized_provider}")

    _validate_provider_verification(provider_verification, normalized_provider)
    _validate_child_provider(child_resolution, normalized_provider)

    direct_rows = _strict_direct_rows(provider_verification, normalized_provider)
    child_rows = _strict_child_rows(child_resolution, normalized_provider)
    exact_urls = {
        _compact(row.get("final_url") or row.get("url"))
        for row in [*direct_rows, *child_rows]
        if _compact(row.get("final_url") or row.get("url"))
    }
    routes = _group_routes(
        provider=normalized_provider,
        direct_rows=direct_rows,
        child_rows=child_rows,
    )

    evaluated = {
        "evaluation_status": "EVALUATED_FOR_ROUTE_REPLICATION",
        "search_hit_count": _search_hit_count(benchmark, normalized_provider),
        "provider_unique_url_count": int(provider_verification.get("provider_unique_url_count") or 0),
        "verified_original_page_count": int(provider_verification.get("page_fetches_succeeded") or 0),
        "eligible_aggregate_parent_count": int(child_resolution.get("eligible_parent_count") or 0),
        "child_page_fetches_succeeded": int(child_resolution.get("child_page_fetches_succeeded") or 0),
        "direct_exact_lot_count": len(direct_rows),
        "child_exact_lot_count": len(child_rows),
        "end_to_end_exact_lot_count": len(exact_urls),
        "successful_route_count": len(routes),
        "successful_markets": sorted({row["market_code"] for row in routes if row["market_code"]}),
        "automatic_activation": False,
    }
    not_evaluated = {
        "evaluation_status": "NOT_EVALUATED",
        "search_hit_count": 0,
        "provider_unique_url_count": 0,
        "verified_original_page_count": 0,
        "eligible_aggregate_parent_count": 0,
        "child_page_fetches_succeeded": 0,
        "direct_exact_lot_count": 0,
        "child_exact_lot_count": 0,
        "end_to_end_exact_lot_count": 0,
        "successful_route_count": 0,
        "successful_markets": [],
        "automatic_activation": False,
    }

    providers = {
        "exa": evaluated if normalized_provider == "exa" else dict(not_evaluated),
        "brave": dict(not_evaluated),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "run_id": run,
        "observed_at": _utc_text(observed_at),
        "observation_scope": OBSERVATION_SCOPE,
        "query_mode": "exact_lot",
        "required_project_domain": CLOTHING_INVENTORY,
        "evaluated_provider": normalized_provider,
        "providers": providers,
        "successful_routes": routes,
        "observed_provider_leader": "NOT_EVALUATED",
        "provider_preference_status": "PROVIDER_COMPARISON_NOT_EVALUATED",
        "learning_interpretation_guard": (
            "This observation can replicate a provider-specific route but cannot compare providers. A provider win requires separate symmetric Exa-vs-Brave evidence."
        ),
        "automatic_provider_activation": False,
        "automatic_source_promotion": False,
        "production_query_mutation": False,
        "production_mutation": False,
    }
