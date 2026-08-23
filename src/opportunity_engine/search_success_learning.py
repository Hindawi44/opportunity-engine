"""Positive learning from end-to-end verified Exact-Lot search success.

The existing learning stack is intentionally strong at learning from misses
(QUERY_GAP). This module adds the symmetric positive side: remember which
provider/market/query/navigation route actually reached strict item-specific
clothing lots.

A single successful run is only an observation. It never activates a provider,
mutates a production query pack, promotes a source, or contacts a seller.
Independent live replications are required before a route/provider is marked
REPLICATED_FOR_REVIEW, and even that state remains review-only.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from opportunity_engine.discovery.exa_shadow_page_verification import EXACT_LOT_CANDIDATE
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY

SCHEMA_VERSION = "search-success-learning-1.0"
MEMORY_SCHEMA_VERSION = "search-success-memory-1.0"
_SUPPORTED_PROVIDERS = ("exa", "brave")
_STRICT_EXACT_EVIDENCE = (
    "inventory_evidence",
    "direct_sale_evidence",
    "item_specific_url_evidence",
    "price_evidence",
    "quantity_evidence",
)


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _provider_name(value: object) -> str:
    return _compact(value).casefold()


def _utc_text(value: str | None) -> str:
    if value:
        return _compact(value)
    return datetime.now(timezone.utc).isoformat()


def _domain(url: object) -> str:
    try:
        return (urlsplit(_compact(url)).hostname or "").casefold()
    except ValueError:
        return ""


def _strict_exact_lot(row: Mapping[str, Any], *, expected_provider: str | None = None) -> bool:
    if row.get("classification") != EXACT_LOT_CANDIDATE:
        return False
    if row.get("fetch_ok") is False:
        return False
    if expected_provider and _provider_name(row.get("provider")) not in {"", expected_provider}:
        return False
    evidence = row.get("evidence") or {}
    if not isinstance(evidence, Mapping):
        return False
    if _compact(evidence.get("project_domain")) != CLOTHING_INVENTORY:
        return False
    if evidence.get("page_subject_domain") not in {None, CLOTHING_INVENTORY}:
        return False
    return all(evidence.get(field) is True for field in _STRICT_EXACT_EVIDENCE)


def _validate_benchmark(benchmark: Mapping[str, Any]) -> None:
    if benchmark.get("status") != "SUCCESS":
        raise ValueError("benchmark must be SUCCESS")
    if benchmark.get("shadow_only") is not True:
        raise ValueError("benchmark must be shadow-only")
    if _compact(benchmark.get("query_mode")).casefold() != "exact_lot":
        raise ValueError("positive learning requires exact_lot query mode")
    if benchmark.get("project_domain_gate_enforced") is not True:
        raise ValueError("benchmark project domain gate must be enforced")
    if _compact(benchmark.get("project_domain")) != CLOTHING_INVENTORY:
        raise ValueError("benchmark must be CLOTHING_INVENTORY")


def _validate_provider_verification(report: Mapping[str, Any], provider: str) -> None:
    if report.get("status") != "SUCCESS":
        raise ValueError(f"{provider} provider verification must be SUCCESS")
    if _provider_name(report.get("provider")) != provider:
        raise ValueError(f"{provider} provider verification identity mismatch")
    if report.get("shadow_only") is not True:
        raise ValueError(f"{provider} provider verification must be shadow-only")
    if report.get("symmetric_provider_verification") is not True:
        raise ValueError(f"{provider} symmetric provider verification is required")
    if report.get("commercial_specificity_gate_enforced") is not True:
        raise ValueError(f"{provider} commercial specificity gate is required")
    if report.get("project_domain_gate_enforced") is not True:
        raise ValueError(f"{provider} project domain gate is required")
    if _compact(report.get("required_project_domain")) != CLOTHING_INVENTORY:
        raise ValueError(f"{provider} provider verification must require CLOTHING_INVENTORY")


def _validate_child_provider(report: Mapping[str, Any], provider: str) -> None:
    if report.get("status") != "SUCCESS":
        raise ValueError(f"{provider} child resolution must be SUCCESS")
    if _provider_name(report.get("provider")) != provider:
        raise ValueError(f"{provider} child resolution identity mismatch")
    if report.get("shadow_only") is not True:
        raise ValueError(f"{provider} child resolution must be shadow-only")
    if report.get("project_domain_gate_enforced") is not True:
        raise ValueError(f"{provider} child project domain gate is required")
    if _compact(report.get("required_project_domain")) != CLOTHING_INVENTORY:
        raise ValueError(f"{provider} child resolution must require CLOTHING_INVENTORY")
    if report.get("commercial_specificity_gate_enforced") is not True:
        raise ValueError(f"{provider} child commercial specificity gate is required")
    if report.get("child_subject_domain_gate_enforced") is not True:
        raise ValueError(f"{provider} child subject domain gate is required")
    if report.get("same_origin_child_links_only") is not True:
        raise ValueError(f"{provider} same-origin child link guard is required")
    if report.get("descendant_path_child_links_only") is not True:
        raise ValueError(f"{provider} descendant child link guard is required")
    if report.get("exact_lot_acceptance_only") is not True:
        raise ValueError(f"{provider} exact-lot-only child acceptance is required")
    if report.get("production_mutation") is not False:
        raise ValueError(f"{provider} child resolution must not mutate production")


def _strict_direct_rows(report: Mapping[str, Any], provider: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in report.get("verified_pages") or []:
        if not isinstance(raw, Mapping) or not _strict_exact_lot(raw, expected_provider=provider):
            continue
        url = _compact(raw.get("final_url") or raw.get("url"))
        if not url or url in seen:
            continue
        seen.add(url)
        rows.append(dict(raw))
    return rows


def _strict_child_rows(report: Mapping[str, Any], provider: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in report.get("exact_lots") or []:
        if not isinstance(raw, Mapping) or not _strict_exact_lot(raw, expected_provider=provider):
            continue
        url = _compact(raw.get("final_url") or raw.get("url"))
        if not url or url in seen:
            continue
        seen.add(url)
        rows.append(dict(raw))
    return rows


def _search_hit_count(benchmark: Mapping[str, Any], provider: str) -> int:
    total = 0
    for market in benchmark.get("market_results") or []:
        if not isinstance(market, Mapping):
            continue
        provider_row = market.get(provider) or {}
        if not isinstance(provider_row, Mapping):
            continue
        results = provider_row.get("results") or []
        if isinstance(results, Sequence) and not isinstance(results, (str, bytes)):
            total += sum(1 for row in results if isinstance(row, Mapping))
    return total


def _group_routes(
    *,
    provider: str,
    direct_rows: Sequence[Mapping[str, Any]],
    child_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str, str], set[str]] = defaultdict(set)

    for row in direct_rows:
        market = _compact(row.get("market_code")).upper()
        query = _compact(row.get("query"))
        url = _compact(row.get("final_url") or row.get("url"))
        domain = _domain(url)
        key = (provider, market, query, "DIRECT_RESULT", domain)
        if url:
            grouped[key].add(url)

    for row in child_rows:
        market = _compact(row.get("market_code")).upper()
        query = _compact(row.get("query"))
        child_url = _compact(row.get("final_url") or row.get("url"))
        parent_url = _compact(row.get("parent_url"))
        parent_domain = _domain(parent_url)
        key = (provider, market, query, "AGGREGATE_CHILD", parent_domain)
        if child_url:
            grouped[key].add(child_url)

    output: list[dict[str, Any]] = []
    for (one_provider, market, query, pathway, domain), urls in grouped.items():
        output.append(
            {
                "provider": one_provider,
                "market_code": market,
                "query": query,
                "pathway": pathway,
                "parent_domain": domain if pathway == "AGGREGATE_CHILD" else None,
                "result_domain": domain if pathway == "DIRECT_RESULT" else None,
                "exact_lot_count": len(urls),
                "exact_lot_urls": sorted(urls),
            }
        )
    output.sort(
        key=lambda row: (
            row["provider"],
            row["market_code"],
            row["query"],
            row["pathway"],
            row.get("parent_domain") or row.get("result_domain") or "",
        )
    )
    return output


def build_search_success_observation(
    *,
    run_id: str,
    benchmark: Mapping[str, Any],
    tool_learning_proof: Mapping[str, Any],
    child_resolution: Mapping[str, Any],
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Build one immutable, review-only positive-learning observation."""
    run = _compact(run_id)
    if not run:
        raise ValueError("run_id is required")
    _validate_benchmark(benchmark)
    if tool_learning_proof.get("status") != "SUCCESS":
        raise ValueError("tool learning proof must be SUCCESS")
    if tool_learning_proof.get("shadow_only") is not True:
        raise ValueError("tool learning proof must be shadow-only")
    if tool_learning_proof.get("automatic_provider_activation") is not False:
        raise ValueError("tool learning proof must not activate providers")
    if tool_learning_proof.get("production_mutation") is not False:
        raise ValueError("tool learning proof must not mutate production")
    if child_resolution.get("status") != "SUCCESS":
        raise ValueError("child resolution envelope must be SUCCESS")
    if child_resolution.get("shadow_only") is not True:
        raise ValueError("child resolution envelope must be shadow-only")
    if child_resolution.get("production_mutation") is not False:
        raise ValueError("child resolution envelope must not mutate production")

    provider_payload: dict[str, dict[str, Any]] = {}
    successful_routes: list[dict[str, Any]] = []

    for provider in _SUPPORTED_PROVIDERS:
        verification = tool_learning_proof.get(f"{provider}_verification") or {}
        child_report = child_resolution.get(provider) or {}
        if not isinstance(verification, Mapping) or not isinstance(child_report, Mapping):
            raise ValueError(f"{provider} learning inputs must be objects")
        _validate_provider_verification(verification, provider)
        _validate_child_provider(child_report, provider)

        direct_rows = _strict_direct_rows(verification, provider)
        child_rows = _strict_child_rows(child_report, provider)
        unique_exact_urls = {
            _compact(row.get("final_url") or row.get("url"))
            for row in [*direct_rows, *child_rows]
            if _compact(row.get("final_url") or row.get("url"))
        }
        routes = _group_routes(
            provider=provider,
            direct_rows=direct_rows,
            child_rows=child_rows,
        )
        successful_routes.extend(routes)
        provider_payload[provider] = {
            "search_hit_count": _search_hit_count(benchmark, provider),
            "provider_unique_url_count": int(verification.get("provider_unique_url_count") or 0),
            "verified_original_page_count": int(verification.get("page_fetches_succeeded") or 0),
            "eligible_aggregate_parent_count": int(child_report.get("eligible_parent_count") or 0),
            "child_page_fetches_succeeded": int(child_report.get("child_page_fetches_succeeded") or 0),
            "direct_exact_lot_count": len(direct_rows),
            "child_exact_lot_count": len(child_rows),
            "end_to_end_exact_lot_count": len(unique_exact_urls),
            "successful_route_count": len(routes),
            "successful_markets": sorted({row["market_code"] for row in routes if row["market_code"]}),
            "automatic_activation": False,
        }

    exa_count = provider_payload["exa"]["end_to_end_exact_lot_count"]
    brave_count = provider_payload["brave"]["end_to_end_exact_lot_count"]
    if exa_count > brave_count:
        leader = "EXA"
    elif brave_count > exa_count:
        leader = "BRAVE"
    elif exa_count or brave_count:
        leader = "TIE"
    else:
        leader = "NONE"

    if leader in {"EXA", "BRAVE"}:
        preference_status = "SINGLE_RUN_OBSERVATION_ONLY"
    elif leader == "TIE":
        preference_status = "NO_CLEAR_LEADER"
    else:
        preference_status = "NO_VERIFIED_EXACT_LOTS"

    successful_routes.sort(
        key=lambda row: (
            row["provider"], row["market_code"], row["pathway"], row["query"]
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "run_id": run,
        "observed_at": _utc_text(observed_at),
        "query_mode": "exact_lot",
        "required_project_domain": CLOTHING_INVENTORY,
        "providers": provider_payload,
        "successful_routes": successful_routes,
        "observed_provider_leader": leader,
        "provider_preference_status": preference_status,
        "learning_interpretation_guard": (
            "One successful run is evidence, not a provider/query promotion. Independent live replications are required before review-only learning is considered replicated."
        ),
        "automatic_provider_activation": False,
        "automatic_source_promotion": False,
        "production_query_mutation": False,
        "production_mutation": False,
    }


def _route_key(row: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        _provider_name(row.get("provider")),
        _compact(row.get("market_code")).upper(),
        _compact(row.get("query")),
        _compact(row.get("pathway")).upper(),
        _compact(row.get("parent_domain") or row.get("result_domain")).casefold(),
    )


def _empty_memory() -> dict[str, Any]:
    return {
        "schema_version": MEMORY_SCHEMA_VERSION,
        "run_count": 0,
        "observations": [],
        "route_learning": [],
        "provider_learning": {},
        "automatic_provider_activation": False,
        "automatic_source_promotion": False,
        "production_query_mutation": False,
        "production_mutation": False,
    }


def update_search_success_memory(
    existing_memory: Mapping[str, Any] | None,
    observation: Mapping[str, Any],
    *,
    min_independent_runs: int = 2,
    max_observations: int = 100,
) -> dict[str, Any]:
    """Merge one observation and derive conservative replicated learning state."""
    if min_independent_runs < 2:
        raise ValueError("min_independent_runs must be >= 2")
    if max_observations < min_independent_runs:
        raise ValueError("max_observations must be >= min_independent_runs")
    if observation.get("schema_version") != SCHEMA_VERSION or observation.get("status") != "SUCCESS":
        raise ValueError("observation must be a successful search-success-learning report")
    if observation.get("automatic_provider_activation") is not False:
        raise ValueError("observation cannot activate providers")
    if observation.get("production_query_mutation") is not False:
        raise ValueError("observation cannot mutate production queries")

    memory = deepcopy(dict(existing_memory or {})) if existing_memory else _empty_memory()
    if memory.get("schema_version") not in {None, MEMORY_SCHEMA_VERSION}:
        raise ValueError("unsupported search success memory schema")

    prior = [row for row in memory.get("observations") or [] if isinstance(row, Mapping)]
    run_id = _compact(observation.get("run_id"))
    if not run_id:
        raise ValueError("observation run_id is required")
    if not any(_compact(row.get("run_id")) == run_id for row in prior):
        prior.append(deepcopy(dict(observation)))
    prior = prior[-max_observations:]

    route_runs: dict[tuple[str, str, str, str, str], set[str]] = defaultdict(set)
    route_urls: dict[tuple[str, str, str, str, str], set[str]] = defaultdict(set)
    provider_success_runs: dict[str, set[str]] = defaultdict(set)
    provider_exact_urls: dict[str, set[str]] = defaultdict(set)
    provider_markets: dict[str, set[str]] = defaultdict(set)

    for obs in prior:
        obs_run = _compact(obs.get("run_id"))
        providers = obs.get("providers") or {}
        if isinstance(providers, Mapping):
            for provider in _SUPPORTED_PROVIDERS:
                row = providers.get(provider) or {}
                if not isinstance(row, Mapping):
                    continue
                if int(row.get("end_to_end_exact_lot_count") or 0) > 0:
                    provider_success_runs[provider].add(obs_run)
                for market in row.get("successful_markets") or []:
                    if _compact(market):
                        provider_markets[provider].add(_compact(market).upper())

        for route in obs.get("successful_routes") or []:
            if not isinstance(route, Mapping):
                continue
            key = _route_key(route)
            provider = key[0]
            if provider not in _SUPPORTED_PROVIDERS or not key[1] or not key[2] or not key[3]:
                continue
            urls = {_compact(url) for url in route.get("exact_lot_urls") or [] if _compact(url)}
            if not urls:
                continue
            route_runs[key].add(obs_run)
            route_urls[key].update(urls)
            provider_exact_urls[provider].update(urls)

    route_learning: list[dict[str, Any]] = []
    for key, runs in route_runs.items():
        provider, market, query, pathway, domain = key
        replicated = len(runs) >= min_independent_runs
        route_learning.append(
            {
                "provider": provider,
                "market_code": market,
                "query": query,
                "pathway": pathway,
                "parent_domain": domain if pathway == "AGGREGATE_CHILD" else None,
                "result_domain": domain if pathway == "DIRECT_RESULT" else None,
                "independent_run_count": len(runs),
                "supporting_run_ids": sorted(runs),
                "verified_exact_lot_url_count": len(route_urls[key]),
                "verified_exact_lot_urls": sorted(route_urls[key]),
                "status": "REPLICATED_FOR_REVIEW" if replicated else "CANDIDATE",
                "automatic_activation": False,
                "production_query_mutation": False,
            }
        )
    route_learning.sort(
        key=lambda row: (
            -row["independent_run_count"],
            -row["verified_exact_lot_url_count"],
            row["provider"],
            row["market_code"],
            row["query"],
        )
    )

    provider_learning: dict[str, dict[str, Any]] = {}
    for provider in _SUPPORTED_PROVIDERS:
        runs = provider_success_runs[provider]
        if not runs:
            status = "NO_VERIFIED_SUCCESS"
        elif len(runs) >= min_independent_runs:
            status = "REPLICATED_FOR_REVIEW"
        else:
            status = "CANDIDATE"
        provider_learning[provider] = {
            "successful_independent_run_count": len(runs),
            "supporting_run_ids": sorted(runs),
            "verified_exact_lot_url_count": len(provider_exact_urls[provider]),
            "verified_exact_lot_urls": sorted(provider_exact_urls[provider]),
            "successful_markets": sorted(provider_markets[provider]),
            "status": status,
            "automatic_activation": False,
        }

    return {
        "schema_version": MEMORY_SCHEMA_VERSION,
        "run_count": len(prior),
        "observations": [deepcopy(dict(row)) for row in prior],
        "route_learning": route_learning,
        "provider_learning": provider_learning,
        "min_independent_runs_for_replication": min_independent_runs,
        "replicated_route_count": sum(
            1 for row in route_learning if row["status"] == "REPLICATED_FOR_REVIEW"
        ),
        "learning_interpretation_guard": (
            "Replicated learning is review-only. It may guide future shadow search experiments but cannot activate providers, promote sources, or mutate production queries automatically."
        ),
        "automatic_provider_activation": False,
        "automatic_source_promotion": False,
        "production_query_mutation": False,
        "production_mutation": False,
    }
