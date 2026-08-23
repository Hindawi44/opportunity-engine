"""Single-provider route replication learning for strict Exact-Lot evidence.

Tool comparison and route replication answer different questions:

* Tool comparison asks whether Exa or Brave is better and therefore requires
  symmetric evidence from both providers.
* Route replication asks whether a previously observed provider/market/query/
  navigation path independently reaches strict Exact-Lot pages again.

This module implements only the second question. It never declares a provider
leader and never activates a provider or mutates production queries.

Route replication may consume either the original one-hop child resolver or the
bounded same-origin multi-hop resolver. The multi-hop report is accepted only
when its full safety contract is present: clothing-domain gating, child-subject
gating, same-origin navigation, bounded traversal, Exact-Lot-only acceptance,
and no production or commercial actions.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

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


def _validate_multihop_provider(report: Mapping[str, Any], provider: str) -> None:
    if report.get("status") != "SUCCESS":
        raise ValueError(f"{provider} multi-hop resolution must be SUCCESS")
    if _compact(report.get("provider")).casefold() != provider:
        raise ValueError(f"{provider} multi-hop resolution identity mismatch")
    if report.get("shadow_only") is not True:
        raise ValueError(f"{provider} multi-hop resolution must be shadow-only")
    if report.get("project_domain_gate_enforced") is not True:
        raise ValueError(f"{provider} multi-hop project domain gate is required")
    if _compact(report.get("required_project_domain")) != CLOTHING_INVENTORY:
        raise ValueError(f"{provider} multi-hop resolution must require CLOTHING_INVENTORY")
    if report.get("commercial_specificity_gate_enforced") is not True:
        raise ValueError(f"{provider} multi-hop commercial specificity gate is required")
    if report.get("child_subject_domain_gate_enforced") is not True:
        raise ValueError(f"{provider} multi-hop child subject domain gate is required")
    if report.get("same_origin_only") is not True:
        raise ValueError(f"{provider} same-origin multi-hop guard is required")
    if report.get("bounded_multi_hop") is not True:
        raise ValueError(f"{provider} bounded multi-hop guard is required")
    if report.get("exact_lot_acceptance_only") is not True:
        raise ValueError(f"{provider} exact-lot-only multi-hop acceptance is required")
    if report.get("production_mutation") is not False:
        raise ValueError(f"{provider} multi-hop resolution must not mutate production")
    for field in (
        "automatic_contact",
        "automatic_bid",
        "automatic_reservation",
        "automatic_purchase",
        "automatic_payment",
    ):
        if report.get(field) is not False:
            raise ValueError(f"{provider} multi-hop resolution must keep {field}=False")


def _dedupe_exact_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        url = _compact(row.get("final_url") or row.get("url"))
        if not url or url in seen:
            continue
        seen.add(url)
        output.append(dict(row))
    return output


def build_provider_route_success_observation(
    *,
    run_id: str,
    provider: str,
    benchmark: Mapping[str, Any],
    provider_verification: Mapping[str, Any],
    child_resolution: Mapping[str, Any] | None = None,
    multihop_resolution: Mapping[str, Any] | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Build one strict provider-specific route-replication observation.

    This report deliberately carries the same search-success schema used by the
    shared memory updater, but provider comparison fields are explicitly marked
    NOT_EVALUATED so single-provider evidence can never masquerade as a tool win.

    At least one resolved-navigation input is required. When both one-hop and
    multi-hop reports are provided, strict Exact-Lot URLs are deduplicated before
    route learning so the same product cannot receive double credit.
    """
    run = _compact(run_id)
    if not run:
        raise ValueError("run_id is required")
    normalized_provider = _compact(provider).casefold()
    if normalized_provider not in _SUPPORTED_ROUTE_PROVIDERS:
        raise ValueError("provider route replication currently supports exa only")
    if child_resolution is None and multihop_resolution is None:
        raise ValueError("provider route replication requires child or multi-hop resolution")

    _validate_benchmark(benchmark)
    if _compact(benchmark.get("provider_mode")).casefold() != normalized_provider:
        raise ValueError(f"provider route replication requires provider_mode={normalized_provider}")

    _validate_provider_verification(provider_verification, normalized_provider)

    legacy_rows: list[dict[str, Any]] = []
    multihop_rows: list[dict[str, Any]] = []
    eligible_parent_count = 0
    resolved_page_fetches_succeeded = 0

    if child_resolution is not None:
        _validate_child_provider(child_resolution, normalized_provider)
        legacy_rows = _strict_child_rows(child_resolution, normalized_provider)
        eligible_parent_count += int(child_resolution.get("eligible_parent_count") or 0)
        resolved_page_fetches_succeeded += int(
            child_resolution.get("child_page_fetches_succeeded") or 0
        )

    if multihop_resolution is not None:
        _validate_multihop_provider(multihop_resolution, normalized_provider)
        multihop_rows = _strict_child_rows(multihop_resolution, normalized_provider)
        eligible_parent_count += int(multihop_resolution.get("eligible_root_parent_count") or 0)
        resolved_page_fetches_succeeded += int(
            multihop_resolution.get("navigation_page_fetches_succeeded") or 0
        )

    direct_rows = _strict_direct_rows(provider_verification, normalized_provider)
    resolved_rows = _dedupe_exact_rows([*legacy_rows, *multihop_rows])
    exact_urls = {
        _compact(row.get("final_url") or row.get("url"))
        for row in [*direct_rows, *resolved_rows]
        if _compact(row.get("final_url") or row.get("url"))
    }
    routes = _group_routes(
        provider=normalized_provider,
        direct_rows=direct_rows,
        child_rows=resolved_rows,
    )

    evaluated = {
        "evaluation_status": "EVALUATED_FOR_ROUTE_REPLICATION",
        "search_hit_count": _search_hit_count(benchmark, normalized_provider),
        "provider_unique_url_count": int(provider_verification.get("provider_unique_url_count") or 0),
        "verified_original_page_count": int(provider_verification.get("page_fetches_succeeded") or 0),
        "eligible_aggregate_parent_count": eligible_parent_count,
        "child_page_fetches_succeeded": resolved_page_fetches_succeeded,
        "direct_exact_lot_count": len(direct_rows),
        "child_exact_lot_count": len(legacy_rows),
        "multihop_exact_lot_count": len(multihop_rows),
        "resolved_exact_lot_count": len(resolved_rows),
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
        "multihop_exact_lot_count": 0,
        "resolved_exact_lot_count": 0,
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
            "This observation can replicate a provider-specific route, including bounded same-origin multi-hop navigation, but cannot compare providers. A provider win requires separate symmetric Exa-vs-Brave evidence."
        ),
        "automatic_provider_activation": False,
        "automatic_source_promotion": False,
        "production_query_mutation": False,
        "production_mutation": False,
    }
